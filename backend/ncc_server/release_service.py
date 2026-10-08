from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ncc_server.models import AgentRelease, Node
from ncc_server.schemas import AgentReleaseResponse


class ReleaseManifestError(ValueError):
    pass


def _text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ReleaseManifestError(f"{name} is missing or invalid")
    return value


def _response(session: Session, release: AgentRelease) -> AgentReleaseResponse:
    assigned = session.scalar(
        select(func.count()).select_from(Node).where(Node.pending_release_id == release.id)
    ) or 0
    return AgentReleaseResponse(
        release_id=release.id,
        payload_version=release.payload_version,
        channel=release.channel,  # type: ignore[arg-type]
        platform=release.platform,  # type: ignore[arg-type]
        architecture=release.architecture,
        artifact_url=release.artifact_url,
        sha256=release.sha256,
        size_bytes=release.size_bytes,
        signature_key_id=release.signature_key_id,
        signature_value=release.signature_value,
        minimum_core_version=release.minimum_core_version,
        released_at=release.released_at,
        assigned_nodes=assigned,
    )


def register_release(session: Session, manifest: dict[str, object]) -> AgentReleaseResponse:
    """Store a manifest only after validating the signed release envelope."""
    if manifest.get("schema_version") != 1:
        raise ReleaseManifestError("unsupported manifest schema")
    channel = _text(manifest.get("channel"), "channel", 16)
    if channel not in {"beta", "stable"}:
        raise ReleaseManifestError("channel must be beta or stable")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1 or not isinstance(artifacts[0], dict):
        raise ReleaseManifestError("exactly one payload artifact is required")
    artifact: dict[str, Any] = artifacts[0]
    version = _text(artifact.get("payload_version"), "payload_version", 64)
    platform = _text(artifact.get("platform"), "platform", 32)
    if platform not in {"windows", "linux"}:
        raise ReleaseManifestError("platform must be windows or linux")
    architecture = _text(artifact.get("architecture"), "architecture", 32)
    url = _text(artifact.get("url"), "artifact url", 2048)
    if not url.startswith("https://"):
        raise ReleaseManifestError("artifact URL must use HTTPS")
    sha256 = _text(artifact.get("sha256"), "sha256", 64).lower()
    if len(sha256) != 64 or any(letter not in "0123456789abcdef" for letter in sha256):
        raise ReleaseManifestError("sha256 must be a 64 character hexadecimal digest")
    size = artifact.get("size_bytes")
    if not isinstance(size, int) or size <= 0:
        raise ReleaseManifestError("size_bytes must be positive")
    signature = manifest.get("signature")
    if not isinstance(signature, dict) or signature.get("algorithm") != "ed25519":
        raise ReleaseManifestError("an ed25519 signature is required")
    key_id = _text(signature.get("key_id"), "signature key", 64)
    signature_value = _text(signature.get("value"), "signature value", 512)
    published = manifest.get("released_at")
    try:
        released_at = datetime.fromisoformat(_text(published, "released_at", 64).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseManifestError("released_at must be ISO-8601") from exc
    if released_at.tzinfo is None:
        raise ReleaseManifestError("released_at requires a timezone")
    existing = session.scalar(
        select(AgentRelease).where(
            AgentRelease.payload_version == version,
            AgentRelease.channel == channel,
            AgentRelease.platform == platform,
            AgentRelease.architecture == architecture,
        )
    )
    if existing is not None:
        return _response(session, existing)
    release = AgentRelease(
        payload_version=version, channel=channel, platform=platform, architecture=architecture,
        artifact_url=url, sha256=sha256, size_bytes=size, signature_key_id=key_id,
        signature_value=signature_value, minimum_core_version=(
            _text(manifest["minimum_core_version"], "minimum_core_version", 64)
            if manifest.get("minimum_core_version") is not None else None
        ), manifest_json=manifest, released_at=released_at.astimezone(timezone.utc),
    )
    session.add(release)
    session.commit()
    session.refresh(release)
    return _response(session, release)


def list_releases(session: Session) -> list[AgentReleaseResponse]:
    releases = session.scalars(select(AgentRelease).order_by(AgentRelease.released_at.desc())).all()
    return [_response(session, release) for release in releases]


def assign_release(session: Session, node_id: str, release_id: str | None) -> bool:
    node = session.get(Node, node_id)
    if node is None:
        return False
    if release_id is None:
        node.pending_release_id = None
    else:
        release = session.get(AgentRelease, release_id)
        if release is None or release.platform != node.platform:
            return False
        node.pending_release_id = release.id
    session.commit()
    return True


def update_node_channel(session: Session, node_id: str, channel: str) -> bool:
    node = session.get(Node, node_id)
    if node is None:
        return False
    node.update_channel = channel
    session.commit()
    return True


def pending_release(session: Session, node_id: str) -> AgentReleaseResponse | None:
    node = session.get(Node, node_id)
    if node is None or not node.pending_release_id:
        return None
    release = session.get(AgentRelease, node.pending_release_id)
    if release is None or release.platform != node.platform or release.channel != node.update_channel:
        return None
    return _response(session, release)
