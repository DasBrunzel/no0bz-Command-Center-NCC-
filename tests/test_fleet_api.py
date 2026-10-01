from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AgentToken, AuditEvent, Base, Node, TelemetryPoint, utc_now


def make_database(path: Path) -> Database:
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    return database


def seed(database: Database) -> tuple[str, str]:
    now = utc_now()
    with database.session() as session:
        online = Node(
            machine_id="machine-online",
            display_name="Root Server",
            platform="windows",
            approved=True,
            agent_version="0.5.0-beta.1",
            metadata_json={"architecture": "AMD64"},
            last_seen_at=now,
        )
        offline = Node(
            machine_id="machine-offline",
            display_name="Gaming PC",
            platform="linux",
            approved=True,
            last_seen_at=now - timedelta(minutes=10),
        )
        session.add_all([online, offline])
        session.flush()
        session.add_all(
            [
                TelemetryPoint(
                    node_id=online.id,
                    sample_id="11111111-1111-4111-8111-111111111111",
                    recorded_at=now - timedelta(seconds=5),
                    payload={"cpu": {"percent": 10.0}},
                ),
                TelemetryPoint(
                    node_id=online.id,
                    sample_id="22222222-2222-4222-8222-222222222222",
                    recorded_at=now,
                    payload={"cpu": {"percent": 42.0}, "memory": {"percent": 55.0}},
                ),
            ]
        )
        session.commit()
        return online.id, offline.id


def test_fleet_api_is_protected_and_returns_latest_metrics(tmp_path: Path) -> None:
    database = make_database(tmp_path / "fleet.db")
    online_id, _ = seed(database)
    settings = ServerSettings(
        database_url="sqlite+pysqlite://",
        dashboard_token="dashboard-secret",
        dashboard_allow_loopback_without_token=False,
    )
    app = create_app(settings, database)
    headers = {"X-NCC-Dashboard-Token": "dashboard-secret"}

    with TestClient(app) as client:
        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert 'id="root"' in dashboard.text
        assert client.get("/api/v1/fleet/nodes").status_code == 401
        assert client.get(
            "/api/v1/fleet/nodes", headers={"X-NCC-Dashboard-Token": "wrong"}
        ).status_code == 401

        nodes = client.get("/api/v1/fleet/nodes", headers=headers)
        assert nodes.status_code == 200
        assert nodes.headers["cache-control"] == "no-store"
        assert [item["display_name"] for item in nodes.json()] == ["Root Server", "Gaming PC"]
        online = next(item for item in nodes.json() if item["node_id"] == online_id)
        assert online["online"] is True
        assert online["latest"]["metrics"]["cpu"]["percent"] == 42.0

        summary = client.get("/api/v1/fleet/summary", headers=headers).json()
        assert summary["total_nodes"] == 2
        assert summary["online_nodes"] == 1
        assert summary["offline_nodes"] == 1
        assert summary["telemetry_points"] == 2

        telemetry = client.get(
            f"/api/v1/fleet/nodes/{online_id}/telemetry?limit=1", headers=headers
        ).json()
        assert len(telemetry) == 1
        assert telemetry[0]["metrics"]["cpu"]["percent"] == 42.0
        assert client.get("/api/v1/fleet/nodes/missing", headers=headers).status_code == 404

        forgotten = client.delete(f"/api/v1/fleet/nodes/{online_id}", headers=headers)
        assert forgotten.status_code == 204
        assert client.get(f"/api/v1/fleet/nodes/{online_id}", headers=headers).status_code == 404

    with database.session() as session:
        assert session.get(Node, online_id) is None
        assert session.query(TelemetryPoint).count() == 0
        assert session.query(AgentToken).count() == 0
        assert session.query(AuditEvent).filter_by(action="node.forgotten").count() == 1


def test_loopback_dashboard_access_can_be_enabled(tmp_path: Path) -> None:
    database = make_database(tmp_path / "loopback.db")
    app = create_app(
        ServerSettings(
            database_url="sqlite+pysqlite://",
            dashboard_allow_loopback_without_token=True,
        ),
        database,
    )
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.get("/api/v1/fleet/summary")
        assert response.status_code == 200
        assert response.json()["total_nodes"] == 0
