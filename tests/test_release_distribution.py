from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from ncc_server import release_feed
from ncc_server.agent_tokens import issue_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AgentRelease, Base, Node
from ncc_server.release_feed import sync_release_feed
from ncc_server.release_service import version_key
from ncc_server.release_signature import TRUSTED_RELEASE_KEYS, manifest_signature_valid
from pydantic import SecretStr
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "DasBrunzel/no0bz-Command-Center-NCC-"
# The published, really signed 0.6.1 payload manifest.
SIGNED_MANIFEST: dict[str, object] = {
    "channel": "beta",
    "signature": {
        "value": "LlaPQLrm1kmNqdmpRTjqq6XB0kwZWzDkWBLNJhynIHAKBPtvsWeWgg11hPdz4VUPyu/bqrl9G3HCNu+bTyPuDw==",
        "key_id": "ncc-release-2026",
        "algorithm": "ed25519",
    },
    "schema_version": 1,
    "minimum_core_version": "0.6.0-beta.1",
    "artifacts": [{
        "architecture": "x86_64",
        "payload_version": "0.6.1",
        "sha256": "6ff03eef7c24e41107f18bf1f6da2d39caf3b1da3ca448bb980e1ca1428ddb15",
        "size_bytes": 53252858,
        "platform": "windows",
        "url": f"https://github.com/{REPOSITORY}/releases/download/v0.6.1/ncc-payload-0.6.1-windows-x86_64.zip",
    }],
    "released_at": "2026-10-30T12:00:43.4076607Z",
}


def manifest(version: str = "0.6.0-beta.2", channel: str = "beta") -> dict[str, object]:
    return {
        "schema_version": 1,
        "channel": channel,
        "released_at": "2026-10-08T12:00:00Z",
        "minimum_core_version": "0.6.0-beta.1",
        "artifacts": [{
            "payload_version": version,
            "platform": "windows",
            "architecture": "x86_64",
            "url": "https://releases.example.test/ncc-payload.zip",
            "sha256": "a" * 64,
            "size_bytes": 123,
        }],
        "signature": {"algorithm": "ed25519", "key_id": "release-2026", "value": "test-signature"},
    }


def setup_node(tmp_path: Path, agent_version: str | None = None) -> tuple[Database, str, str]:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'release.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        token = issue_agent_token(session, "Windows test", None)
        node = Node(
            machine_id="release-node-123", display_name="Release Node", platform="windows",
            approved=True, agent_version=agent_version,
        )
        session.add(node)
        session.flush()
        token.record.node_id = node.id
        session.commit()
        return database, node.id, token.plaintext


def app_for(database: Database) -> TestClient:
    settings = ServerSettings(
        database_url="sqlite+pysqlite://", dashboard_token=SecretStr("dashboard"), release_feed_enabled=False
    )
    return TestClient(create_app(settings, database))


DASHBOARD = {"X-NCC-Dashboard-Token": "dashboard"}


def set_agent_version(database: Database, node_id: str, version: str) -> None:
    with database.session() as session:
        node = session.get(Node, node_id)
        assert node is not None
        node.agent_version = version
        session.commit()


def test_nodes_follow_the_newest_release_of_their_channel(tmp_path: Path) -> None:
    database, node_id, token = setup_node(tmp_path, agent_version="0.6.0")
    agent = {"Authorization": f"Bearer {token}"}
    with app_for(database) as client:
        assert client.get("/api/v1/releases/pending", headers=agent).json() is None
        for version in ("0.6.0", "0.6.1-rc.1", "0.6.1", "0.6.0-beta.8-dev.6"):
            assert client.post("/api/v1/releases", headers=DASHBOARD, json={"manifest": manifest(version)}).status_code == 201
        assert client.get("/api/v1/releases/pending", headers=agent).json()["payload_version"] == "0.6.1"
        node = client.get(f"/api/v1/fleet/nodes/{node_id}", headers=DASHBOARD).json()
        assert node["pending_release_id"] is None
        assert node["release_target_version"] == "0.6.1"
        # Once the node runs it, nothing is offered again.
        set_agent_version(database, node_id, "0.6.1")
        assert client.get("/api/v1/releases/pending", headers=agent).json() is None
        assert client.put(f"/api/v1/fleet/nodes/{node_id}/update-channel", headers=DASHBOARD, json={"channel": "stable"}).status_code == 204
        assert client.post("/api/v1/releases", headers=DASHBOARD, json={"manifest": manifest("0.7.0")}).status_code == 201
        assert client.get("/api/v1/releases/pending", headers=agent).json() is None


def test_a_pinned_older_release_is_held_back_unless_downgrades_are_allowed(tmp_path: Path) -> None:
    database, node_id, token = setup_node(tmp_path, agent_version="0.6.1")
    agent = {"Authorization": f"Bearer {token}"}
    with app_for(database) as client:
        old = client.post("/api/v1/releases", headers=DASHBOARD, json={"manifest": manifest("0.6.0-beta.3")}).json()
        assert client.put(f"/api/v1/fleet/nodes/{node_id}/release", headers=DASHBOARD, json={"release_id": old["release_id"]}).status_code == 204
        assert client.get("/api/v1/releases/pending", headers=agent).json() is None
        node = client.get(f"/api/v1/fleet/nodes/{node_id}", headers=DASHBOARD).json()
        assert node["release_pin_held_back"] is True
        assert node["release_target_version"] is None
        assert client.put(
            f"/api/v1/fleet/nodes/{node_id}/release", headers=DASHBOARD,
            json={"release_id": old["release_id"], "allow_downgrade": True},
        ).status_code == 204
        assert client.get("/api/v1/releases/pending", headers=agent).json()["payload_version"] == "0.6.0-beta.3"
        # Clearing the pin returns the node to the newest release.
        assert client.put(f"/api/v1/fleet/nodes/{node_id}/release", headers=DASHBOARD, json={"release_id": None}).status_code == 204
        node = client.get(f"/api/v1/fleet/nodes/{node_id}", headers=DASHBOARD).json()
        assert node["release_allow_downgrade"] is False
        assert client.get("/api/v1/releases/pending", headers=agent).json() is None


def test_version_order_matches_the_installer_updater() -> None:
    ordered = [
        "0.5.0-beta.70", "0.6.0-alpha.1", "0.6.0-beta.8-dev.6", "0.6.0-beta.8", "0.6.0-rc.1",
        "0.6.0", "0.6.1-beta.1", "0.6.1", "0.10.0",
    ]
    keys = [version_key(value) for value in ordered]
    assert all(key is not None for key in keys)
    assert keys == sorted(keys)  # type: ignore[type-var]
    assert version_key("local-build") is None


def test_release_signature_uses_the_trusted_release_key() -> None:
    trusted = json.loads((ROOT / "windows" / "installer" / "trusted-keys.json").read_text(encoding="utf-8-sig"))
    assert trusted["keys"] == TRUSTED_RELEASE_KEYS
    assert manifest_signature_valid(SIGNED_MANIFEST)
    tampered = copy.deepcopy(SIGNED_MANIFEST)
    tampered["artifacts"][0]["sha256"] = "0" * 64  # type: ignore[index]
    assert not manifest_signature_valid(tampered)
    assert not manifest_signature_valid(manifest())


def test_release_feed_registers_only_signed_manifests_from_the_repository(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'feed.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    release_feed._seen_assets.clear()
    release_feed._status["registered"] = []
    downloads = f"https://github.com/{REPOSITORY}/releases/download"
    forged = copy.deepcopy(SIGNED_MANIFEST)
    forged["artifacts"][0]["payload_version"] = "9.9.9"  # type: ignore[index]
    elsewhere = copy.deepcopy(SIGNED_MANIFEST)
    elsewhere["artifacts"][0]["url"] = "https://example.test/ncc-payload.zip"  # type: ignore[index]
    files = {
        f"{downloads}/v0.6.1/ncc-payload-0.6.1-windows-x86_64.zip.manifest.json": SIGNED_MANIFEST,
        f"{downloads}/v9.9.9/ncc-payload-9.9.9-windows-x86_64.zip.manifest.json": forged,
        f"{downloads}/v0.6.2/ncc-payload-0.6.2-windows-x86_64.zip.manifest.json": elsewhere,
    }
    releases = [
        {"draft": False, "assets": [{"id": index, "name": url.rsplit("/", 1)[1], "browser_download_url": url}]}
        for index, url in enumerate(files, start=1)
    ]
    releases.append({"draft": False, "assets": [
        {"id": 50, "name": "ncc-agent-setup-0.6.1-windows-x86_64.exe.manifest.json", "browser_download_url": f"{downloads}/v0.6.1/setup.json"},
        {"id": 51, "name": "ncc-payload-0.6.3-windows-x86_64.zip.manifest.json", "browser_download_url": "https://example.test/other.json"},
    ]})
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?", 1)[0]
        requested.append(url)
        if url == f"https://api.github.com/repos/{REPOSITORY}/releases":
            return httpx.Response(200, json=releases)
        # Real assets carry a byte order mark.
        return httpx.Response(200, content=b"\xef\xbb\xbf" + json.dumps(files[url]).encode())

    settings = ServerSettings(database_url="sqlite+pysqlite://", release_feed_repository=REPOSITORY)

    async def run() -> list[str]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await sync_release_feed(database, settings, client)

    assert asyncio.run(run()) == ["0.6.1"]
    with database.session() as session:
        assert [release.payload_version for release in session.scalars(select(AgentRelease))] == ["0.6.1"]
    assert "https://example.test/other.json" not in requested
    assert f"{downloads}/v0.6.1/setup.json" not in requested
    # A second check only lists the releases again.
    requested.clear()
    assert asyncio.run(run()) == []
    assert requested == [f"https://api.github.com/repos/{REPOSITORY}/releases"]
    status = release_feed.feed_status(settings)
    assert status.error is None and status.registered == ["0.6.1"]
