use serde::Deserialize;

#[derive(Debug, Deserialize, PartialEq, Eq)]
pub struct PayloadHealth {
    pub payload_version: String,
    pub status: String,
}

/// Payloads write this secret-free JSON to the Core state directory after startup.
pub fn is_healthy(active_version: &str, raw: &[u8]) -> Result<bool, String> {
    let health: PayloadHealth =
        serde_json::from_slice(raw).map_err(|_| "invalid payload health record")?;
    Ok(health.payload_version == active_version && health.status == "ready")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_the_active_payload_can_report_ready() {
        assert!(
            is_healthy(
                "0.6.0-beta.1",
                br#"{"payload_version":"0.6.0-beta.1","status":"ready"}"#
            )
            .unwrap()
        );
        assert!(
            !is_healthy(
                "0.6.0-beta.1",
                br#"{"payload_version":"0.6.0-beta.2","status":"ready"}"#
            )
            .unwrap()
        );
        assert!(
            !is_healthy(
                "0.6.0-beta.1",
                br#"{"payload_version":"0.6.0-beta.1","status":"starting"}"#
            )
            .unwrap()
        );
    }
}
