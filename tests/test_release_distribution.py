from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.agent_tokens import issue_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base, Node
from pydantic import SecretStr


def manifest(channel: str = "beta") -> dict[str, object]:
    return {
        "schema_version": 1,
        "channel": channel,
        "released_at": "2026-10-08T12:00:00Z",
        "minimum_core_version": "0.6.0-beta.1",
        "artifacts": [{
            "payload_version": "0.6.0-beta.2",
            "platform": "windows",
            "architecture": "x86_64",
            "url": "https://releases.example.test/ncc-payload.zip",
            "sha256": "a" * 64,
            "size_bytes": 123,
        }],
        "signature": {"algorithm": "ed25519", "key_id": "release-2026", "value": "test-signature"},
    }


def test_release_requires_explicit_matching_node_approval(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'release.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        token = issue_agent_token(session, "Windows test", None)
        node = Node(machine_id="release-node-123", display_name="Release Node", platform="windows", approved=True)
        session.add(node)
        session.flush()
        token.record.node_id = node.id
        session.commit()
        node_id = node.id
    app = create_app(ServerSettings(database_url="sqlite+pysqlite://", dashboard_token=SecretStr("dashboard")), database)
    dashboard = {"X-NCC-Dashboard-Token": "dashboard"}
    agent = {"Authorization": f"Bearer {token.plaintext}"}
    with TestClient(app) as client:
        created = client.post("/api/v1/releases", headers=dashboard, json={"manifest": manifest()})
        assert created.status_code == 201
        release_id = created.json()["release_id"]
        assert client.get("/api/v1/releases/pending", headers=agent).json() is None
        assert client.put(f"/api/v1/fleet/nodes/{node_id}/release", headers=dashboard, json={"release_id": release_id}).status_code == 204
        pending = client.get("/api/v1/releases/pending", headers=agent)
        assert pending.status_code == 200
        assert pending.json()["payload_version"] == "0.6.0-beta.2"
        assert client.put(f"/api/v1/fleet/nodes/{node_id}/update-channel", headers=dashboard, json={"channel": "stable"}).status_code == 204
        assert client.get("/api/v1/releases/pending", headers=agent).json() is None
