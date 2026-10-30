"""Register signed payload manifests from the project's GitHub releases.

Together with nodes that follow the newest release, a payload reaches every
device once its GitHub release exists, without registering or assigning it in
the dashboard. Only manifests that a trusted release key signed and whose
payload lies in the same repository's release downloads are registered.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import func, select

from ncc_server import __version__
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AgentRelease
from ncc_server.release_service import ReleaseManifestError, register_release
from ncc_server.release_signature import manifest_signature_valid
from ncc_server.schemas import ReleaseFeedStatusResponse

logger = logging.getLogger(__name__)
_MAX_MANIFEST_BYTES = 64 * 1024

# Per process: what the last check found, and manifest assets already handled
# so a check only downloads new ones.
_status: dict[str, Any] = {"checked_at": None, "error": None, "registered": []}
_seen_assets: set[int] = set()


def feed_status(settings: ServerSettings) -> ReleaseFeedStatusResponse:
    return ReleaseFeedStatusResponse(
        enabled=settings.release_feed_enabled,
        repository=settings.release_feed_repository,
        checked_at=_status["checked_at"],
        error=_status["error"],
        registered=list(_status["registered"]),
    )


def _manifest_assets(releases: object, repository: str) -> list[tuple[int, str]]:
    prefix = f"https://github.com/{repository}/releases/download/"
    found: list[tuple[int, str]] = []
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        for asset in release.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            name, url, asset_id = asset.get("name"), asset.get("browser_download_url"), asset.get("id")
            if (
                isinstance(name, str) and name.startswith("ncc-payload-") and name.endswith(".zip.manifest.json")
                and isinstance(url, str) and url.startswith(prefix) and isinstance(asset_id, int)
            ):
                found.append((asset_id, url))
    return found


def _artifact_in_repository(manifest: dict[str, Any], repository: str) -> bool:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1 or not isinstance(artifacts[0], dict):
        return False
    url = artifacts[0].get("url")
    return isinstance(url, str) and url.startswith(f"https://github.com/{repository}/releases/download/")


async def sync_release_feed(
    database: Database, settings: ServerSettings, client: httpx.AsyncClient | None = None
) -> list[str]:
    """Register new signed manifests; returns the payload versions added."""
    repository = settings.release_feed_repository
    added: list[str] = []
    own_client = client is None
    http = client or httpx.AsyncClient(
        timeout=20, follow_redirects=True,
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"ncc-server/{__version__}"},
    )
    try:
        response = await http.get(f"https://api.github.com/repos/{repository}/releases", params={"per_page": 20})
        response.raise_for_status()
        for asset_id, url in _manifest_assets(response.json(), repository):
            if asset_id in _seen_assets:
                continue
            download = await http.get(url)
            download.raise_for_status()
            if len(download.content) > _MAX_MANIFEST_BYTES:
                logger.warning("Release manifest %s is too large; skipped", url)
                _seen_assets.add(asset_id)
                continue
            # The build writes the manifest with a UTF-8 byte order mark.
            try:
                manifest = json.loads(download.content.decode("utf-8-sig"))
            except ValueError:
                manifest = None
            if not isinstance(manifest, dict) or not _artifact_in_repository(manifest, repository):
                logger.warning("Release manifest %s points outside %s; skipped", url, repository)
            elif not manifest_signature_valid(manifest):
                logger.warning("Release manifest %s has no valid trusted signature; skipped", url)
            else:
                with database.session() as session:
                    before = session.scalar(select(func.count()).select_from(AgentRelease)) or 0
                    try:
                        release = register_release(session, manifest)
                    except ReleaseManifestError as exc:
                        logger.warning("Release manifest %s is invalid: %s", url, exc)
                    else:
                        if (session.scalar(select(func.count()).select_from(AgentRelease)) or 0) > before:
                            added.append(release.payload_version)
                            logger.info("Registered payload %s from GitHub", release.payload_version)
            _seen_assets.add(asset_id)
        _status["error"] = None
    except Exception as exc:
        _status["error"] = str(exc) or exc.__class__.__name__
        raise
    finally:
        _status["checked_at"] = datetime.now(timezone.utc)
        _status["registered"] = [*_status["registered"], *added][-10:]
        if own_client:
            await http.aclose()
    return added
