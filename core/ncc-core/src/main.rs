mod signature;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
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
    if let Err(error) = run(env::args().skip(1).collect()) {
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
        _ => return Err("expected status, stage, activate or health".to_owned()),
    }
    Ok(())
}

fn parse_state_dir(args: Vec<String>) -> Result<(PathBuf, Vec<String>)> {
    let mut state_dir = None;
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
    let destination = root.join("payloads").join(version).join("payload.archive");
    let parent = destination.parent().ok_or("payload path has no parent")?;
    fs::create_dir_all(parent).map_err(display)?;
    let temporary = destination.with_extension("tmp");
    fs::copy(source, &temporary).map_err(display)?;
    if sha256(&temporary)? != hash {
        return Err("staged artifact SHA-256 mismatch".to_owned());
    }
    fs::rename(temporary, destination).map_err(display)?;
    Ok(())
}

fn activate(root: &Path, args: &[String]) -> Result<()> {
    let version = valid_version(&value(args, "--version")?)?;
    if !root
        .join("payloads")
        .join(&version)
        .join("payload.archive")
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
    use std::fs;

    fn args(root: &Path, rest: &[&str]) -> Vec<String> {
        let mut result = vec!["--state-dir".to_owned(), root.display().to_string()];
        result.extend(rest.iter().map(|value| (*value).to_owned()));
        result
    }

    #[test]
    fn a_failed_health_check_rolls_back() {
        let root = env::temp_dir().join(format!("ncc-core-test-{}", now_unix().unwrap()));
        let source = root.join("source.zip");
        fs::create_dir_all(&root).unwrap();
        fs::write(&source, b"first").unwrap();
        let hash = sha256(&source).unwrap();
        run(args(
            &root,
            &[
                "stage",
                "--source",
                &source.display().to_string(),
                "--version",
                "0.6.0-beta.1",
                "--sha256",
                &hash,
                "--size",
                "5",
            ],
        ))
        .unwrap();
        run(args(&root, &["activate", "--version", "0.6.0-beta.1"])).unwrap();
        run(args(
            &root,
            &["health", "--version", "0.6.0-beta.1", "--healthy", "true"],
        ))
        .unwrap();
        fs::write(&source, b"second").unwrap();
        let hash = sha256(&source).unwrap();
        run(args(
            &root,
            &[
                "stage",
                "--source",
                &source.display().to_string(),
                "--version",
                "0.6.0-beta.2",
                "--sha256",
                &hash,
                "--size",
                "6",
            ],
        ))
        .unwrap();
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
