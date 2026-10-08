from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class ManifestError(ValueError):
    """The release manifest or an artifact did not meet the Core contract."""


@dataclass(frozen=True)
class ReleaseArtifact:
    payload_version: str
    platform: str
    architecture: str
    url: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ReleaseManifest:
    schema_version: int
    channel: str
    released_at: str
    minimum_core_version: str | None
    artifacts: tuple[ReleaseArtifact, ...]
    signature_algorithm: str
    signature_key_id: str
    signature_value: str

    def artifact_for(self, platform: str, architecture: str) -> ReleaseArtifact:
        matches = [
            artifact
            for artifact in self.artifacts
            if artifact.platform == platform and artifact.architecture == architecture
        ]
        if len(matches) != 1:
            raise ManifestError(f"expected exactly one artifact for {platform}/{architecture}")
        return matches[0]


def load_manifest(value: Mapping[str, Any]) -> ReleaseManifest:
    if value.get("schema_version") != 1:
        raise ManifestError("unsupported manifest schema")
    channel = _string(value, "channel")
    if channel not in {"stable", "beta"}:
        raise ManifestError("invalid release channel")
    minimum_core_version = value.get("minimum_core_version")
    if minimum_core_version is not None and (
        not isinstance(minimum_core_version, str) or not VERSION_PATTERN.fullmatch(minimum_core_version)
    ):
        raise ManifestError("invalid minimum core version")
    raw_artifacts = value.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ManifestError("manifest needs at least one artifact")
    artifacts = tuple(_artifact(item) for item in raw_artifacts)
    if len({(item.platform, item.architecture) for item in artifacts}) != len(artifacts):
        raise ManifestError("manifest contains duplicate platform artifacts")
    signature = value.get("signature")
    if not isinstance(signature, Mapping) or signature.get("algorithm") != "ed25519":
        raise ManifestError("manifest requires an ed25519 signature")
    return ReleaseManifest(
        schema_version=1,
        channel=channel,
        released_at=_string(value, "released_at"),
        minimum_core_version=minimum_core_version,
        artifacts=artifacts,
        signature_algorithm="ed25519",
        signature_key_id=_string(signature, "key_id"),
        signature_value=_string(signature, "value"),
    )


def verify_artifact(path: Path, artifact: ReleaseArtifact) -> None:
    if not path.is_file():
        raise ManifestError("artifact is missing")
    if path.stat().st_size != artifact.size_bytes:
        raise ManifestError("artifact size does not match manifest")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != artifact.sha256:
        raise ManifestError("artifact SHA-256 does not match manifest")


def _artifact(value: object) -> ReleaseArtifact:
    if not isinstance(value, Mapping):
        raise ManifestError("invalid artifact")
    version = _string(value, "payload_version")
    sha256 = _string(value, "sha256")
    if not VERSION_PATTERN.fullmatch(version) or not SHA256_PATTERN.fullmatch(sha256):
        raise ManifestError("invalid artifact version or SHA-256")
    platform = _string(value, "platform")
    architecture = _string(value, "architecture")
    if platform not in {"windows", "linux"} or architecture not in {"x86_64", "aarch64"}:
        raise ManifestError("unsupported artifact platform")
    url = _string(value, "url")
    if not url.startswith("https://"):
        raise ManifestError("artifact URL must use HTTPS")
    size = value.get("size_bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ManifestError("invalid artifact size")
    return ReleaseArtifact(version, platform, architecture, url, sha256, size)


def _string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ManifestError(f"missing or invalid {key}")
    return result
