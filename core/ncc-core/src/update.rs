use serde::Deserialize;
use std::env;
use std::fs;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct PendingRelease {
    pub payload_version: String,
    pub artifact_url: String,
    pub sha256: String,
    pub size_bytes: u64,
    pub signature_key_id: String,
    pub signature_value: String,
}

pub fn request_pending_release() -> Result<Option<PendingRelease>, String> {
    let server = env::var("NCC_AGENT_SERVER_URL")
        .map_err(|_| "NCC_AGENT_SERVER_URL is required for update checks")?;
    let token = env::var("NCC_AGENT_TOKEN")
        .map_err(|_| "NCC_AGENT_TOKEN is required for update checks")?;
    let url = format!("{}/api/v1/releases/pending", server.trim_end_matches('/'));
    let mut response = ureq::get(&url)
        .header("Authorization", &format!("Bearer {token}"))
        .call()
        .map_err(|error| format!("release request failed: {error}"))?;
    let body = response
        .body_mut()
        .read_to_string()
        .map_err(|error| format!("release response is unreadable: {error}"))?;
    serde_json::from_str::<Option<PendingRelease>>(&body)
        .map_err(|error| format!("release response is invalid: {error}"))
}

pub fn download(root: &Path, release: &PendingRelease) -> Result<std::path::PathBuf, String> {
    if !release.artifact_url.starts_with("https://") {
        return Err("release artifact URL must use HTTPS".to_owned());
    }
    let downloads = root.join("downloads");
    fs::create_dir_all(&downloads).map_err(|error| error.to_string())?;
    let destination = downloads.join(format!("{}.zip", release.payload_version));
    let temporary = destination.with_extension("tmp");
    let mut response = ureq::get(&release.artifact_url)
        .call()
        .map_err(|error| format!("release download failed: {error}"))?;
    let bytes = response
        .body_mut()
        .read_to_vec()
        .map_err(|error| format!("release download is unreadable: {error}"))?;
    if bytes.len() as u64 != release.size_bytes {
        return Err("downloaded release size does not match manifest".to_owned());
    }
    fs::write(&temporary, bytes).map_err(|error| error.to_string())?;
    fs::rename(temporary, &destination).map_err(|error| error.to_string())?;
    Ok(destination)
}
