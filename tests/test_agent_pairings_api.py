from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AgentToken, Base, Node


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


def test_pairing_rebinds_an_existing_machine_and_revokes_its_old_credential(tmp_path: Path) -> None:
    database = make_database(tmp_path / "pairing-rebind.db")
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token="dashboard-secret"),
        database,
    )
    dashboard = {"X-NCC-Dashboard-Token": "dashboard-secret"}
    payload = pairing_payload()
    with database.session() as session:
        node = Node(
            machine_id=str(payload["machine_id"]),
            display_name="Existing Laptop",
            platform="linux",
            approved=True,
        )
        session.add(node)
        session.flush()
        old_token = AgentToken(name="old credential", token_hash="old-token-hash", node_id=node.id)
        session.add(old_token)
        session.commit()
        old_token_id = old_token.id
        node_id = node.id

    with TestClient(app) as client:
        assert client.post("/api/v1/agent-pairings/register", json=payload).status_code == 201
        assert client.post(
            f"/api/v1/agent-pairings/{payload['pairing_id']}/approve", headers=dashboard
        ).status_code == 200
        claimed = client.post(
            f"/api/v1/agent-pairings/{payload['pairing_id']}/claim",
            json={"pairing_secret": payload["pairing_secret"]},
        )
        assert claimed.status_code == 200

    with database.session() as session:
        old_token = session.get(AgentToken, old_token_id)
        rebound = session.query(AgentToken).filter(AgentToken.token_hash != "old-token-hash").one()
        assert old_token is not None and old_token.revoked_at is not None
        assert rebound.node_id == node_id


def test_beta_dashboard_approval_marks_the_claimed_node(tmp_path: Path) -> None:
    database = make_database(tmp_path / "pairing-beta-role.db")
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token="dashboard-secret"),
        database,
    )
    payload = pairing_payload()
    commander_headers = {"X-NCC-Dashboard-Token": "dashboard-secret"}
    with TestClient(app) as commander:
        created = commander.post(
            "/api/v1/admin-codes",
            headers=commander_headers,
            json={"label": "Beta friend", "beta_tester": True},
        )
        assert created.status_code == 201
        with TestClient(app) as beta:
            assert beta.post(
                "/api/v1/admin-codes/redeem", json={"code": created.json()["code"]}
            ).status_code == 200
            assert commander.post("/api/v1/agent-pairings/register", json=payload).status_code == 201
            approved = beta.post(
                f"/api/v1/agent-pairings/{payload['pairing_id']}/approve"
            )
            assert approved.status_code == 200
            assert approved.json()["access_role"] == "beta_tester"
            claimed = beta.post(
                f"/api/v1/agent-pairings/{payload['pairing_id']}/claim",
                json={"pairing_secret": payload["pairing_secret"]},
            )
            assert claimed.status_code == 200
            enrolled = beta.post(
                "/api/v1/nodes/enroll",
                headers={"Authorization": f"Bearer {claimed.json()['token']}"},
                json={
                    "machine_id": payload["machine_id"],
                    "display_name": payload["display_name"],
                    "platform": payload["platform"],
                    "agent_version": payload["agent_version"],
                    "metadata": payload["metadata"],
                },
            )
            assert enrolled.status_code == 200
            assert enrolled.json()["access_role"] == "beta_tester"
            fleet = beta.get("/api/v1/fleet/nodes")
            assert fleet.status_code == 200
            assert fleet.json()[0]["access_role"] == "beta_tester"
