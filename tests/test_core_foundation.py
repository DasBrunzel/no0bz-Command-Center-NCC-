from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from ncc_core.controller import CoreController
from ncc_core.manifest import ManifestError, ReleaseArtifact, load_manifest, verify_artifact


def artifact_for(path: Path, version: str = "0.6.0-beta.1") -> ReleaseArtifact:
    return ReleaseArtifact(
        payload_version=version,
        platform="windows",
        architecture="x86_64",
        url="https://releases.example.test/ncc-agent.zip",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
    )


def test_manifest_requires_signed_unique_https_artifacts() -> None:
    manifest = load_manifest(
        {
            "schema_version": 1,
            "channel": "beta",
            "released_at": "2026-10-08T12:00:00Z",
            "minimum_core_version": "0.6.0-beta.1",
            "artifacts": [
                {
                    "payload_version": "0.6.0-beta.2",
                    "platform": "windows",
                    "architecture": "x86_64",
                    "url": "https://releases.example.test/windows.zip",
                    "sha256": "a" * 64,
                    "size_bytes": 123,
                }
            ],
            "signature": {"algorithm": "ed25519", "key_id": "release-2026", "value": "test-signature"},
        }
    )
    assert manifest.artifact_for("windows", "x86_64").payload_version == "0.6.0-beta.2"
    with pytest.raises(ManifestError, match="HTTPS"):
        load_manifest(
            {
                "schema_version": 1,
                "channel": "beta",
                "released_at": "2026-10-08T12:00:00Z",
                "artifacts": [
                    {
                        "payload_version": "0.6.0-beta.2",
                        "platform": "windows",
                        "architecture": "x86_64",
                        "url": "http://unsafe.example.test/a.zip",
                        "sha256": "a" * 64,
                        "size_bytes": 1,
                    }
                ],
                "signature": {"algorithm": "ed25519", "key_id": "key", "value": "signature"},
            }
        )


def test_core_stages_valid_artifact_without_touching_source(tmp_path: Path) -> None:
    source = tmp_path / "release.zip"
    source.write_bytes(b"payload-v1")
    controller = CoreController(tmp_path / "core")
    staged = controller.stage(source, artifact_for(source))
    assert staged.read_bytes() == b"payload-v1"
    assert source.read_bytes() == b"payload-v1"
    assert controller.state().health == "inactive"


def test_core_rejects_tampered_artifact(tmp_path: Path) -> None:
    source = tmp_path / "release.zip"
    source.write_bytes(b"payload-v1")
    artifact = artifact_for(source)
    source.write_bytes(b"tampered")
    with pytest.raises(ManifestError, match="size|SHA-256"):
        verify_artifact(source, artifact)


def test_failed_health_rolls_back_to_previous_payload(tmp_path: Path) -> None:
    controller = CoreController(tmp_path / "core")
    one = tmp_path / "one.zip"
    two = tmp_path / "two.zip"
    one.write_bytes(b"payload-one")
    two.write_bytes(b"payload-two")
    controller.stage(one, artifact_for(one, "0.6.0-beta.1"))
    controller.stage(two, artifact_for(two, "0.6.0-beta.2"))
    assert controller.activate("0.6.0-beta.1").health == "awaiting_health"
    assert controller.report_health("0.6.0-beta.1", True).health == "healthy"
    assert controller.activate("0.6.0-beta.2").previous_payload == "0.6.0-beta.1"
    rolled_back = controller.report_health("0.6.0-beta.2", False)
    assert rolled_back.active_payload == "0.6.0-beta.1"
    assert rolled_back.health == "rolled_back"
