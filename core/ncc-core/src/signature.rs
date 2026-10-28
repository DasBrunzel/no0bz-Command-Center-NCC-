use base64::{Engine as _, engine::general_purpose::STANDARD};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

/// Stable, unambiguous metadata bound to a staged release archive.
///
/// The production signer signs exactly these UTF-8 bytes. A signature therefore
/// cannot be reused for another version, size or SHA-256 value.
pub fn release_statement(version: &str, sha256: &str, size_bytes: u64) -> String {
    format!("NCC-AGENT-RELEASE-V1\n{version}\n{sha256}\n{size_bytes}\n")
}

pub fn installer_statement(version: &str, sha256: &str, size_bytes: u64, url: &str) -> String {
    format!("NCC-AGENT-INSTALLER-V1\n{version}\n{sha256}\n{size_bytes}\n{url}\n")
}

fn verify_statement(
    public_key_base64: &str,
    signature_base64: &str,
    statement: &str,
) -> Result<(), String> {
    let key_bytes = STANDARD
        .decode(public_key_base64)
        .map_err(|_| "invalid Ed25519 public key encoding")?;
    let key_array: [u8; 32] = key_bytes
        .try_into()
        .map_err(|_| "invalid Ed25519 public key length")?;
    let key = VerifyingKey::from_bytes(&key_array).map_err(|_| "invalid Ed25519 public key")?;
    let signature_bytes = STANDARD
        .decode(signature_base64)
        .map_err(|_| "invalid Ed25519 signature encoding")?;
    let signature =
        Signature::from_slice(&signature_bytes).map_err(|_| "invalid Ed25519 signature length")?;
    key.verify(statement.as_bytes(), &signature)
        .map_err(|_| "release signature verification failed".to_owned())
}

pub fn verify_release_signature(
    version: &str,
    sha256: &str,
    size_bytes: u64,
    public_key_base64: &str,
    signature_base64: &str,
) -> Result<(), String> {
    verify_statement(
        public_key_base64,
        signature_base64,
        &release_statement(version, sha256, size_bytes),
    )
}

#[derive(Deserialize)]
struct TrustedKeys {
    keys: BTreeMap<String, String>,
}

pub fn verify_trusted_release_signature(
    core_root: &Path,
    key_id: &str,
    version: &str,
    sha256: &str,
    size_bytes: u64,
    signature_base64: &str,
) -> Result<(), String> {
    let public_key = trusted_key(core_root, key_id)?;
    verify_release_signature(version, sha256, size_bytes, &public_key, signature_base64)
}

fn trusted_key(core_root: &Path, key_id: &str) -> Result<String, String> {
    let path = core_root.join("config").join("trusted-keys.json");
    let raw = fs::read(path).map_err(|_| "trusted key configuration is unavailable")?;
    let trusted: TrustedKeys =
        serde_json::from_slice(&raw).map_err(|_| "invalid trusted key configuration")?;
    trusted
        .keys
        .get(key_id)
        .cloned()
        .ok_or("release key is not trusted".to_owned())
}

pub fn verify_trusted_installer_signature(
    core_root: &Path,
    key_id: &str,
    version: &str,
    sha256: &str,
    size_bytes: u64,
    url: &str,
    signature_base64: &str,
) -> Result<(), String> {
    let public_key = trusted_key(core_root, key_id)?;
    verify_statement(
        &public_key,
        signature_base64,
        &installer_statement(version, sha256, size_bytes, url),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Signer, SigningKey};

    #[test]
    fn a_signature_is_bound_to_the_exact_release_statement() {
        let signing_key = SigningKey::from_bytes(&[7_u8; 32]);
        let statement = release_statement("0.6.0-beta.1", &"a".repeat(64), 42);
        let signature = signing_key.sign(statement.as_bytes());
        let public_key = STANDARD.encode(signing_key.verifying_key().as_bytes());
        let encoded_signature = STANDARD.encode(signature.to_bytes());
        assert!(
            verify_release_signature(
                "0.6.0-beta.1",
                &"a".repeat(64),
                42,
                &public_key,
                &encoded_signature,
            )
            .is_ok()
        );
        assert!(
            verify_release_signature(
                "0.6.0-beta.2",
                &"a".repeat(64),
                42,
                &public_key,
                &encoded_signature,
            )
            .is_err()
        );
    }

    #[test]
    fn installer_signature_is_bound_to_version_hash_size_and_url() {
        let signing_key = SigningKey::from_bytes(&[9_u8; 32]);
        let statement = installer_statement(
            "0.6.0-beta.8",
            &"b".repeat(64),
            500,
            "https://example.test/setup.exe",
        );
        let signature = STANDARD.encode(signing_key.sign(statement.as_bytes()).to_bytes());
        let key = STANDARD.encode(signing_key.verifying_key().as_bytes());
        assert!(verify_statement(&key, &signature, &statement).is_ok());
        assert!(
            verify_statement(
                &key,
                &signature,
                &installer_statement(
                    "0.6.0-beta.9",
                    &"b".repeat(64),
                    500,
                    "https://example.test/setup.exe"
                )
            )
            .is_err()
        );
        assert!(
            verify_statement(
                &key,
                &signature,
                &installer_statement(
                    "0.6.0-beta.8",
                    &"b".repeat(64),
                    500,
                    "https://evil.test/setup.exe"
                )
            )
            .is_err()
        );
    }
}
