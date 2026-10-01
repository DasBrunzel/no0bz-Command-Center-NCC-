from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.agent_tokens import hash_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AgentToken, AuditEvent, Base


def make_database(path: Path) -> Database:
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    return database


def test_dashboard_can_issue_list_and_revoke_invitations(tmp_path: Path) -> None:
    database = make_database(tmp_path / "invitations.db")
    app = create_app(
        ServerSettings(
            database_url="sqlite+pysqlite://",
            dashboard_token="dashboard-secret",
            dashboard_allow_loopback_without_token=False,
        ),
        database,
    )
    headers = {"X-NCC-Dashboard-Token": "dashboard-secret"}

    with TestClient(app) as client:
        assert client.get("/api/v1/agent-invitations").status_code == 401
        response = client.post(
            "/api/v1/agent-invitations",
            headers=headers,
            json={"name": "  CachyOS   Laptop  ", "expires_hours": 24},
        )
        assert response.status_code == 201
        created = response.json()
        plaintext = created["token"]
        assert plaintext.startswith("ncc_agent_")
        assert created["name"] == "CachyOS Laptop"
        assert created["status"] == "ready"
        assert created["expires_at"] is not None

        listed = client.get("/api/v1/agent-invitations", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert "token" not in listed.json()[0]

        with database.session() as session:
            record = session.get(AgentToken, created["token_id"])
            assert record is not None
            assert record.token_hash == hash_agent_token(plaintext)
            assert plaintext not in record.token_hash

        revoked = client.post(
            f"/api/v1/agent-invitations/{created['token_id']}/revoke", headers=headers
        )
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        assert client.get("/api/v1/agent-invitations", headers=headers).json() == []
        removed = client.delete(
            f"/api/v1/agent-invitations/{created['token_id']}", headers=headers
        )
        assert removed.status_code == 204
        assert client.get("/api/v1/agent-invitations", headers=headers).json() == []

    with database.session() as session:
        record = session.get(AgentToken, created["token_id"])
        assert record is None
        audit_events = session.query(AuditEvent).all()
        assert [event.actor_type for event in audit_events] == ["dashboard", "dashboard"]


def test_invitation_without_expiry_is_supported(tmp_path: Path) -> None:
    database = make_database(tmp_path / "never-expires.db")
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token="dashboard-secret"),
        database,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent-invitations",
            headers={"X-NCC-Dashboard-Token": "dashboard-secret"},
            json={"name": "Lab node", "expires_hours": 0},
        )
    assert response.status_code == 201
    assert response.json()["expires_at"] is None
