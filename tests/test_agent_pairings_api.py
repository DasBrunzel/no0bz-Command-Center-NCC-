from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base


def make_database(path: Path) -> Database:
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    return database


def pairing_payload() -> dict[str, object]:
    return {
        "pairing_id": "pairing_example_123456",
        "pairing_secret": "a" * 43,
        "machine_id": "machine-12345678",
        "display_name": "CachyOS Laptop",
        "platform": "linux",
        "agent_version": "0.5.0-beta.8",
        "metadata": {"architecture": "x86_64"},
    }


def test_dashboard_approves_pairing_and_agent_claims_internal_token(tmp_path: Path) -> None:
    database = make_database(tmp_path / "pairing.db")
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token="dashboard-secret"),
        database,
    )
    dashboard = {"X-NCC-Dashboard-Token": "dashboard-secret"}
    payload = pairing_payload()
    with TestClient(app) as client:
        registered = client.post("/api/v1/agent-pairings/register", json=payload)
        assert registered.status_code == 201
        assert registered.json()["status"] == "waiting"
        assert client.post(
            f"/api/v1/agent-pairings/{payload['pairing_id']}/claim",
            json={"pairing_secret": payload["pairing_secret"]},
        ).status_code == 409

        approved = client.post(
            f"/api/v1/agent-pairings/{payload['pairing_id']}/approve", headers=dashboard
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        claimed = client.post(
            f"/api/v1/agent-pairings/{payload['pairing_id']}/claim",
            json={"pairing_secret": payload["pairing_secret"]},
        )
        assert claimed.status_code == 200
        assert claimed.json()["token"].startswith("ncc_agent_")
        assert client.post(
            f"/api/v1/agent-pairings/{payload['pairing_id']}/claim",
            json={"pairing_secret": payload["pairing_secret"]},
        ).status_code == 409


def test_pairing_never_exposes_its_secret_to_dashboard(tmp_path: Path) -> None:
    database = make_database(tmp_path / "pairing-list.db")
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token="dashboard-secret"),
        database,
    )
    payload = pairing_payload()
    with TestClient(app) as client:
        assert client.post("/api/v1/agent-pairings/register", json=payload).status_code == 201
        listed = client.get(
            "/api/v1/agent-pairings", headers={"X-NCC-Dashboard-Token": "dashboard-secret"}
        )
    assert listed.status_code == 200
    assert "pairing_secret" not in listed.text
    assert "secret_hash" not in listed.text
