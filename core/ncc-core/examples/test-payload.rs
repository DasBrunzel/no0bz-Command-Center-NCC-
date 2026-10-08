//! Deliberately harmless payload used only for the opt-in Core migration test.
//! It writes the normal ready record and does not collect or upload telemetry.

use serde_json::json;
use std::{env, fs, thread, time::Duration};

fn main() {
    let state_dir = env::var("NCC_CORE_STATE_DIR").expect("Core state directory is required");
    let version =
        env::var("NCC_TEST_PAYLOAD_VERSION").unwrap_or_else(|_| "0.6.0-beta.test".to_owned());
    let path = std::path::Path::new(&state_dir).join("payload-health.json");
    fs::create_dir_all(&state_dir).expect("create state directory");
    fs::write(
        path,
        json!({"payload_version": version, "status": "ready"}).to_string(),
    )
    .expect("write health record");
    loop {
        thread::sleep(Duration::from_secs(60));
    }
}
