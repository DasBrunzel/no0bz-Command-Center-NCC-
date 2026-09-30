from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.agent_tokens import hash_agent_token, issue_agent_token, revoke_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AgentToken, Base, Node, utc_now
from sqlalchemy import select


def make_database(path: Path) -> Database:
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    return database


def issue(database: Database, name: str = "Test Agent") -> tuple[str, str]:
    with database.session() as session:
        issued = issue_agent_token(session, name, utc_now() + timedelta(hours=1))
        return issued.record.id, issued.plaintext


def enrollment_payload(machine_id: str = "machine-12345678") -> dict[str, object]:
    return {
        "machine_id": machine_id,
        "display_name": "Gaming PC",
        "platform": "windows",
        "agent_version": "0.5.0-alpha.2",
        "metadata": {"architecture": "amd64"},
    }


def test_token_enrollment_and_heartbeat_are_persistent(tmp_path: Path) -> None:
    path = tmp_path / "ncc.db"
    database = make_database(path)
    token_id, plaintext = issue(database)
    settings = ServerSettings(
        database_url=f"sqlite+pysqlite:///{path.as_posix()}",
        heartbeat_interval_seconds=12,
    )
    app = create_app(settings, database)
    headers = {"Authorization": f"Bearer {plaintext}"}

    with TestClient(app) as client:
        enrollment = client.post("/api/v1/nodes/enroll", json=enrollment_payload(), headers=headers)
        assert enrollment.status_code == 200
        node_id = enrollment.json()["node_id"]
        assert enrollment.json()["approved"] is True
        assert enrollment.json()["online"] is True
        assert enrollment.json()["heartbeat_interval_seconds"] == 12

        heartbeat = client.post(
            "/api/v1/nodes/heartbeat",
            json={"agent_version": "0.5.0-alpha.2", "metadata": {"tailscale": True}},
            headers=headers,
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["node_id"] == node_id
        assert heartbeat.json()["next_heartbeat_seconds"] == 12
        assert client.get("/api/v1/nodes/me", headers=headers).status_code == 200

    reopened = make_database(path)
    with reopened.session() as session:
        token = session.get(AgentToken, token_id)
        node = session.scalar(select(Node).where(Node.machine_id == "machine-12345678"))
        assert token is not None
        assert token.token_hash == hash_agent_token(plaintext)
        assert token.token_hash != plaintext
        assert token.node_id == node_id
        assert token.last_used_at is not None
        assert node is not None
        assert node.metadata_json == {"tailscale": True}
        assert node.last_seen_at is not None
    reopened.dispose()


def test_invalid_expired_and_revoked_tokens_are_rejected(tmp_path: Path) -> None:
    database = make_database(tmp_path / "auth.db")
    active_id, active = issue(database)
    with database.session() as session:
        expired = issue_agent_token(session, "Expired", utc_now() - timedelta(seconds=1))
        expired_plaintext = expired.plaintext

    app = create_app(ServerSettings(database_url="sqlite+pysqlite://"), database)
    with TestClient(app) as client:
        assert client.get("/api/v1/nodes/me").status_code == 401
        assert client.get(
            "/api/v1/nodes/me", headers={"Authorization": "Bearer invalid"}
        ).status_code == 401
        assert client.post(
            "/api/v1/nodes/enroll",
            json=enrollment_payload(),
            headers={"Authorization": f"Bearer {expired_plaintext}"},
        ).status_code == 401

        enrolled = client.post(
            "/api/v1/nodes/enroll",
            json=enrollment_payload(),
            headers={"X-NCC-Agent-Token": active},
        )
        assert enrolled.status_code == 200
        with database.session() as session:
            assert revoke_agent_token(session, active_id)
        assert client.get(
            "/api/v1/nodes/me", headers={"X-NCC-Agent-Token": active}
        ).status_code == 401


def test_token_cannot_claim_an_existing_machine(tmp_path: Path) -> None:
    database = make_database(tmp_path / "identity.db")
    _, first = issue(database, "First")
    _, second = issue(database, "Second")
    app = create_app(ServerSettings(database_url="sqlite+pysqlite://"), database)

    with TestClient(app) as client:
        first_response = client.post(
            "/api/v1/nodes/enroll",
            json=enrollment_payload(),
            headers={"Authorization": f"Bearer {first}"},
        )
        assert first_response.status_code == 200
        conflict = client.post(
            "/api/v1/nodes/enroll",
            json=enrollment_payload(),
            headers={"Authorization": f"Bearer {second}"},
        )
        assert conflict.status_code == 409

        unbound_heartbeat = client.post(
            "/api/v1/nodes/heartbeat",
            json={"agent_version": "0.5.0-alpha.2"},
            headers={"Authorization": f"Bearer {second}"},
        )
        assert unbound_heartbeat.status_code == 409
