mod health;
mod payload;
mod signature;
mod update;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use signature::verify_trusted_release_signature;
use std::env;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

type Result<T> = std::result::Result<T, String>;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum Health {
    Inactive,
    AwaitingHealth,
    Healthy,
    RolledBack,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
struct CoreState {
    active_payload: Option<String>,
    previous_payload: Option<String>,
    last_update_unix: Option<u64>,
    health: Health,
}

impl Default for CoreState {
    fn default() -> Self {
        Self {
            active_payload: None,
            previous_payload: None,
            last_update_unix: None,
            health: Health::Inactive,
        }
    }
}

fn main() {
    // Signature verification can exceed the small default Windows main-thread
    // stack on some MSVC builds. Run the complete command on a bounded larger
    // worker stack so malformed releases produce an error, never a crash.
    let args: Vec<String> = env::args().skip(1).collect();
    let outcome = std::thread::Builder::new()
        .name("ncc-core".to_owned())
        .stack_size(8 * 1024 * 1024)
        .spawn(move || run(args))
        .map_err(display)
        .and_then(|worker| {
            worker
                .join()
                .map_err(|_| "NCC Core worker panicked".to_owned())
        });
    if let Err(error) = outcome.and_then(|result| result) {
        eprintln!("ncc-core: {error}");
        std::process::exit(2);
    }
}

fn run(args: Vec<String>) -> Result<()> {
    let (state_dir, remaining) = parse_state_dir(args)?;
    let command = remaining.first().ok_or("missing command")?.as_str();
    match command {
        "status" => print_state(&load_state(&state_dir)?),
        "stage" => stage(&state_dir, &remaining[1..])?,
        "activate" => activate(&state_dir, &remaining[1..])?,
        "health" => report_health(&state_dir, &remaining[1..])?,
        "run-payload" => run_payload(&state_dir, &remaining[1..])?,
        "check-update" => check_update(&state_dir)?,
        "service" => run_service(&state_dir)?,
        _ => return Err("expected status, stage, activate, health, check-update or run-payload".to_owned()),
    }
    Ok(())
}

/// Windows/systemd hosts invoke this fixed command.  Its inputs are environment
/// variables from a local ACL-protected config file; it never evaluates a shell.
fn run_service(root: &Path) -> Result<()> {
    // An approved update is checked only at a controlled service start.  A
    // failed request, untrusted key, or bad artifact never blocks the proven
    // active payload from monitoring the host.
    if let Err(error) = check_update(root) {
        eprintln!("ncc-core: update check skipped: {error}");
    }
    let timeout = env::var("NCC_CORE_HEALTH_TIMEOUT_SECONDS").unwrap_or_else(|_| "30".to_owned());
    let state = load_state(root)?;
    let version = state
        .active_payload
        .ok_or("no active, signed NCC payload")?;
    let descriptor = payload_descriptor(root, &version)?;
    run_payload(
        root,
        &[
            "--version".to_owned(),
            version,
            "--executable".to_owned(),
            descriptor.executable.display().to_string(),
            "--timeout-seconds".to_owned(),
            timeout,
        ],
    )
}

fn check_update(root: &Path) -> Result<()> {
    let Some(release) = update::request_pending_release()? else {
        println!("{{\"update\":\"none\"}}");
        return Ok(());
    };
    let current = load_state(root)?;
    if current.active_payload.as_deref() == Some(&release.payload_version) {
        println!("{{\"update\":\"already-active\"}}");
        return Ok(());
    }
    let source = update::download(root, &release)?;
    stage(
        root,
        &[
            "--source".to_owned(), source.display().to_string(),
            "--version".to_owned(), release.payload_version.clone(),
            "--sha256".to_owned(), release.sha256,
            "--size".to_owned(), release.size_bytes.to_string(),
            "--key-id".to_owned(), release.signature_key_id,
            "--signature".to_owned(), release.signature_value,
        ],
    )?;
    activate(root, &["--version".to_owned(), release.payload_version])
}

#[derive(Deserialize)]
struct PayloadDescriptorFile {
    executable: String,
    #[serde(default)]
    arguments: Vec<String>,
}

struct PayloadDescriptor {
    executable: PathBuf,
    arguments: Vec<String>,
}

fn payload_descriptor(root: &Path, version: &str) -> Result<PayloadDescriptor> {
    let payload_root = root.join("payloads").join(version).join("files");
    payload_descriptor_from(&payload_root)
}

fn run_payload(root: &Path, args: &[String]) -> Result<()> {
    let version = valid_version(&value(args, "--version")?)?;
    let executable = PathBuf::from(value(args, "--executable")?);
    let timeout: u64 = value(args, "--timeout-seconds")?.parse().map_err(display)?;
    let state = load_state(root)?;
    if state.active_payload.as_deref() != Some(&version) {
        return Err("payload version is not active".to_owned());
    }
    let state_dir = root.join("state");
    let health_file = state_dir.join("payload-health.json");
    // A health record is only valid for the process launched below.
    let _ = fs::remove_file(&health_file);
    let arguments = {
        let provided = values(args, "--argument");
        if provided.is_empty() {
            payload_descriptor(root, &version)?.arguments
        } else {
            provided
        }
    };
    let mut child = payload::start(&executable, &arguments, &state_dir, &version)?;
    let ready = payload::wait_for_ready(
        &state_dir,
        &version,
        std::time::Duration::from_secs(timeout),
    )?;
    if ready {
        report_health(
            root,
            &[
                "--version".to_owned(),
                version.clone(),
                "--healthy".to_owned(),
                "true".to_owned(),
            ],
        )?;
        let status = child.wait().map_err(display)?;
        return Err(format!("payload exited after readiness: {status}"));
    }
    let _ = child.kill();
    report_health(
        root,
        &[
            "--version".to_owned(),
            version,
            "--healthy".to_owned(),
            "false".to_owned(),
        ],
    )
}

fn values(args: &[String], key: &str) -> Vec<String> {
    args.windows(2)
        .filter(|pair| pair[0] == key)
        .map(|pair| pair[1].clone())
        .collect()
}

fn parse_state_dir(args: Vec<String>) -> Result<(PathBuf, Vec<String>)> {
    let mut state_dir = env::var_os("NCC_CORE_STATE_DIR").map(PathBuf::from);
    let mut remaining = Vec::new();
    let mut values = args.into_iter();
    while let Some(value) = values.next() {
        if value == "--state-dir" {
            state_dir = Some(PathBuf::from(
                values.next().ok_or("--state-dir needs a value")?,
            ));
        } else {
            remaining.push(value);
            remaining.extend(values);
            break;
        }
    }
    Ok((state_dir.ok_or("--state-dir is required")?, remaining))
}

fn state_path(root: &Path) -> PathBuf {
    root.join("state").join("core-state.json")
}

fn load_state(root: &Path) -> Result<CoreState> {
    let path = state_path(root);
    if !path.exists() {
        return Ok(CoreState::default());
    }
    serde_json::from_slice(&fs::read(path).map_err(display)?).map_err(display)
}

fn save_state(root: &Path, state: &CoreState) -> Result<()> {
    let path = state_path(root);
    let parent = path.parent().ok_or("state path has no parent")?;
    fs::create_dir_all(parent).map_err(display)?;
    let temporary = path.with_extension("tmp");
    let encoded = serde_json::to_vec_pretty(state).map_err(display)?;
    fs::write(&temporary, encoded).map_err(display)?;
    fs::rename(temporary, path).map_err(display)
}

fn stage(root: &Path, args: &[String]) -> Result<()> {
    let source = value(args, "--source")?;
    let version = valid_version(&value(args, "--version")?)?;
    let expected_hash = value(args, "--sha256")?.to_ascii_lowercase();
    let expected_size: u64 = value(args, "--size")?.parse().map_err(display)?;
    let key_id = value(args, "--key-id")?;
    let signature = value(args, "--signature")?;
    let source = PathBuf::from(source);
    let metadata = fs::metadata(&source).map_err(display)?;
    if metadata.len() != expected_size {
        return Err("artifact size does not match manifest".to_owned());
    }
    let hash = sha256(&source)?;
    if hash != expected_hash
        || expected_hash.len() != 64
        || !expected_hash.bytes().all(|byte| byte.is_ascii_hexdigit())
    {
        return Err("artifact SHA-256 does not match manifest".to_owned());
    }
    verify_trusted_release_signature(root, &key_id, &version, &hash, expected_size, &signature)?;
    let destination = root.join("payloads").join(&version).join("payload.archive");
    let parent = destination.parent().ok_or("payload path has no parent")?;
    fs::create_dir_all(parent).map_err(display)?;
    let temporary = destination.with_extension("tmp");
    fs::copy(source, &temporary).map_err(display)?;
    if sha256(&temporary)? != hash {
        return Err("staged artifact SHA-256 mismatch".to_owned());
    }
    fs::rename(temporary, destination).map_err(display)?;
    extract_payload(root, &version)?;
    Ok(())
}

fn extract_payload(root: &Path, version: &str) -> Result<()> {
    let archive_path = root.join("payloads").join(version).join("payload.archive");
    let files = root.join("payloads").join(version).join("files");
    let temporary = files.with_extension("tmp");
    let _ = fs::remove_dir_all(&temporary);
    fs::create_dir_all(&temporary).map_err(display)?;
    let archive = fs::File::open(archive_path).map_err(display)?;
    let mut archive = zip::ZipArchive::new(archive).map_err(display)?;
    for index in 0..archive.len() {
        let mut entry = archive.by_index(index).map_err(display)?;
        let enclosed = entry
            .enclosed_name()
            .ok_or("payload archive contains unsafe path")?
            .to_owned();
        let destination = temporary.join(enclosed);
        if entry.is_dir() {
            fs::create_dir_all(&destination).map_err(display)?;
        } else {
            let parent = destination.parent().ok_or("payload entry has no parent")?;
            fs::create_dir_all(parent).map_err(display)?;
            let mut target = fs::File::create(destination).map_err(display)?;
            std::io::copy(&mut entry, &mut target).map_err(display)?;
            // ZIP does not automatically restore executable bits.  Preserve a
            // payload's Unix mode so the same signed archive format can run
            // under systemd on Linux as well as under Windows.
            #[cfg(unix)]
            if let Some(mode) = entry.unix_mode() {
                use std::os::unix::fs::PermissionsExt;
                fs::set_permissions(
                    temporary.join(enclosed),
                    fs::Permissions::from_mode(mode),
                )
                .map_err(display)?;
            }
        }
    }
    if !temporary.join("payload.json").is_file() {
        return Err("payload archive misses payload.json".to_owned());
    }
    let _ = payload_descriptor_from(&temporary)?;
    let _ = fs::remove_dir_all(&files);
    fs::rename(temporary, files).map_err(display)
}

fn payload_descriptor_from(payload_root: &Path) -> Result<PayloadDescriptor> {
    let descriptor: PayloadDescriptorFile =
        serde_json::from_slice(&fs::read(payload_root.join("payload.json")).map_err(display)?)
            .map_err(display)?;
    let executable_path = Path::new(&descriptor.executable);
    if descriptor.executable.is_empty()
        || executable_path.is_absolute()
        || !executable_path
            .components()
            .all(|component| matches!(component, std::path::Component::Normal(_)))
    {
        return Err("payload descriptor executable is invalid".to_owned());
    }
    let executable = payload_root.join(executable_path);
    if !executable.is_file() {
        return Err("payload descriptor executable is invalid".to_owned());
    }
    Ok(PayloadDescriptor {
        executable,
        arguments: descriptor.arguments,
    })
}

fn activate(root: &Path, args: &[String]) -> Result<()> {
    let version = valid_version(&value(args, "--version")?)?;
    if !root
        .join("payloads")
        .join(&version)
        .join("files")
        .join("payload.json")
        .is_file()
    {
        return Err("payload is not staged".to_owned());
    }
    let current = load_state(root)?;
    let state = CoreState {
        previous_payload: if current.active_payload.as_deref() == Some(&version) {
            current.previous_payload
        } else {
            current.active_payload
        },
        active_payload: Some(version),
        last_update_unix: Some(now_unix()?),
        health: Health::AwaitingHealth,
    };
    save_state(root, &state)?;
    print_state(&state);
    Ok(())
}

fn report_health(root: &Path, args: &[String]) -> Result<()> {
    let version = valid_version(&value(args, "--version")?)?;
    let healthy = value(args, "--healthy")?.parse::<bool>().map_err(display)?;
    let current = load_state(root)?;
    if current.active_payload.as_deref() != Some(&version) {
        return Err("health report is not for the active payload".to_owned());
    }
    let state = if healthy {
        CoreState {
            health: Health::Healthy,
            ..current
        }
    } else if let Some(previous) = current.previous_payload {
        CoreState {
            active_payload: Some(previous),
            previous_payload: Some(version),
            last_update_unix: Some(now_unix()?),
            health: Health::RolledBack,
        }
    } else {
        CoreState {
            active_payload: None,
            previous_payload: Some(version),
            last_update_unix: Some(now_unix()?),
            health: Health::RolledBack,
        }
    };
    save_state(root, &state)?;
    print_state(&state);
    Ok(())
}

fn value(args: &[String], key: &str) -> Result<String> {
    args.windows(2)
        .find(|pair| pair[0] == key)
        .map(|pair| pair[1].clone())
        .ok_or_else(|| format!("{key} is required"))
}

fn valid_version(value: &str) -> Result<String> {
    if value.is_empty()
        || value.len() > 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'.' || byte == b'-')
    {
        return Err("invalid payload version".to_owned());
    }
    Ok(value.to_owned())
}

fn sha256(path: &Path) -> Result<String> {
    let mut source = fs::File::open(path).map_err(display)?;
    let mut digest = Sha256::new();
    let mut buffer = [0_u8; 1024 * 1024];
    loop {
        let count = source.read(&mut buffer).map_err(display)?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn now_unix() -> Result<u64> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_secs())
        .map_err(display)
}

fn print_state(state: &CoreState) {
    println!(
        "{}",
        serde_json::to_string(state).expect("CoreState always serializes")
    );
}

fn display(error: impl std::fmt::Display) -> String {
    error.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::{Engine as _, engine::general_purpose::STANDARD};
    use ed25519_dalek::{Signer, SigningKey};
    use std::fs;
    use std::io::Write;

    fn args(root: &Path, rest: &[&str]) -> Vec<String> {
        let mut result = vec!["--state-dir".to_owned(), root.display().to_string()];
        result.extend(rest.iter().map(|value| (*value).to_owned()));
        result
    }

    fn stage_args(root: &Path, source: &Path, version: &str, hash: &str, size: u64) -> Vec<String> {
        let signing_key = SigningKey::from_bytes(&[9_u8; 32]);
        let public_key = STANDARD.encode(signing_key.verifying_key().as_bytes());
        let config = root.join("config");
        fs::create_dir_all(&config).unwrap();
        fs::write(
            config.join("trusted-keys.json"),
            format!(r#"{{"keys":{{"test-key":"{public_key}"}}}}"#),
        )
        .unwrap();
        let signature = STANDARD.encode(
            signing_key
                .sign(signature::release_statement(version, hash, size).as_bytes())
                .to_bytes(),
        );
        vec![
            "--state-dir".to_owned(),
            root.display().to_string(),
            "stage".to_owned(),
            "--source".to_owned(),
            source.display().to_string(),
            "--version".to_owned(),
            version.to_owned(),
            "--sha256".to_owned(),
            hash.to_owned(),
            "--size".to_owned(),
            size.to_string(),
            "--key-id".to_owned(),
            "test-key".to_owned(),
            "--signature".to_owned(),
            signature,
        ]
    }

    fn payload_archive(path: &Path, executable: &[u8]) {
        let file = fs::File::create(path).unwrap();
        let mut archive = zip::ZipWriter::new(file);
        let options = zip::write::SimpleFileOptions::default();
        archive.start_file("payload.json", options).unwrap();
        archive
            .write_all(br#"{"executable":"payload.bin"}"#)
            .unwrap();
        archive.start_file("payload.bin", options).unwrap();
        archive.write_all(executable).unwrap();
        archive.finish().unwrap();
    }

    #[test]
    fn a_failed_health_check_rolls_back() {
        let root = env::temp_dir().join(format!("ncc-core-test-{}", now_unix().unwrap()));
        let source = root.join("source.zip");
        fs::create_dir_all(&root).unwrap();
        payload_archive(&source, b"first");
        let hash = sha256(&source).unwrap();
        let size = fs::metadata(&source).unwrap().len();
        run(stage_args(&root, &source, "0.6.0-beta.1", &hash, size)).unwrap();
        run(args(&root, &["activate", "--version", "0.6.0-beta.1"])).unwrap();
        run(args(
            &root,
            &["health", "--version", "0.6.0-beta.1", "--healthy", "true"],
        ))
        .unwrap();
        payload_archive(&source, b"second");
        let hash = sha256(&source).unwrap();
        let size = fs::metadata(&source).unwrap().len();
        run(stage_args(&root, &source, "0.6.0-beta.2", &hash, size)).unwrap();
        run(args(&root, &["activate", "--version", "0.6.0-beta.2"])).unwrap();
        run(args(
            &root,
            &["health", "--version", "0.6.0-beta.2", "--healthy", "false"],
        ))
        .unwrap();
        assert_eq!(
            load_state(&root).unwrap().active_payload.as_deref(),
            Some("0.6.0-beta.1")
        );
        fs::remove_dir_all(root).unwrap();
    }
}
