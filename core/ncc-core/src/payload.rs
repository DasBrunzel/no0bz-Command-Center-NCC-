use crate::health::is_healthy;
use std::fs;
use std::path::Path;
use std::process::{Child, Command};
use std::thread;
use std::time::{Duration, Instant};

/// Starts an already staged payload without a shell. Core will later supply only
/// a release-local executable and fixed arguments.
pub fn start(
    executable: &Path,
    arguments: &[String],
    state_dir: &Path,
    version: &str,
) -> Result<Child, String> {
    Command::new(executable)
        .args(arguments)
        .env("NCC_CORE_STATE_DIR", state_dir)
        .env("NCC_TEST_PAYLOAD_VERSION", version)
        .spawn()
        .map_err(|error| format!("could not start payload: {error}"))
}

/// Wait for the active payload's secret-free ready record.
pub fn wait_for_ready(state_dir: &Path, version: &str, timeout: Duration) -> Result<bool, String> {
    let health_file = state_dir.join("payload-health.json");
    let deadline = Instant::now() + timeout;
    loop {
        match fs::read(&health_file) {
            Ok(raw) if is_healthy(version, &raw)? => return Ok(true),
            Ok(_) | Err(_) => {}
        }
        if Instant::now() >= deadline {
            return Ok(false);
        }
        thread::sleep(Duration::from_millis(100));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn waits_for_the_matching_ready_record() {
        let root = std::env::temp_dir().join(format!("ncc-core-health-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        fs::write(
            root.join("payload-health.json"),
            br#"{"payload_version":"0.6.0-beta.1","status":"ready"}"#,
        )
        .unwrap();
        assert!(wait_for_ready(&root, "0.6.0-beta.1", Duration::from_millis(1)).unwrap());
        assert!(!wait_for_ready(&root, "0.6.0-beta.2", Duration::from_millis(1)).unwrap());
        fs::remove_dir_all(root).unwrap();
    }
}
