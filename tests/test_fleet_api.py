from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import (
    AgentToken,
    AlertState,
    AuditEvent,
    Base,
    Node,
    TelemetryPoint,
    utc_now,
)
from ncc_server.node_service import is_online


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

        groups = client.get("/api/v1/fleet/groups", headers=headers)
        assert groups.status_code == 200
        assert [item["name"] for item in groups.json()] == [
            "PCS & LAPTOPS", "SERVER", "MOBILE", "FRIENDS"
        ]
        created_group = client.post(
            "/api/v1/fleet/groups", headers=headers, json={"name": "Gaming"}
        )
        assert created_group.status_code == 201
        layout = client.put(
            "/api/v1/fleet/layout",
            headers=headers,
            json={"placements": [{"node_id": online_id, "group_id": created_group.json()["group_id"], "position": 0}]},
        )
        assert layout.status_code == 204
        placed = client.get("/api/v1/fleet/nodes", headers=headers).json()
        assert next(item for item in placed if item["node_id"] == online_id)["fleet_group_id"] == created_group.json()["group_id"]

        summary = client.get("/api/v1/fleet/summary", headers=headers).json()
        assert summary["total_nodes"] == 2
        assert summary["online_nodes"] == 1
        assert summary["offline_nodes"] == 1
        assert summary["telemetry_points"] == 2

        with database.session() as session:
            session.add(
                AlertState(
                    node_id=online_id,
                    kind="cpu",
                    severity="critical",
                    active=True,
                    message="Root Server: CPU-Auslastung bei 98 % (critical).",
                )
            )
            session.commit()
        alerts = client.get("/api/v1/fleet/alerts", headers=headers)
        assert alerts.status_code == 200
        assert alerts.json()[0]["display_name"] == "Root Server"
        assert alerts.json()[0]["active"] is True

        telemetry = client.get(
            f"/api/v1/fleet/nodes/{online_id}/telemetry?limit=1", headers=headers
        ).json()
        assert len(telemetry) == 1
        assert telemetry[0]["metrics"]["cpu"]["percent"] == 42.0
        assert client.get("/api/v1/fleet/nodes/missing", headers=headers).status_code == 404

        renamed = client.patch(
            f"/api/v1/fleet/nodes/{online_id}",
            headers=headers,
            json={"display_name": "  Horst   Server  "},
        )
        assert renamed.status_code == 200
        assert renamed.json()["display_name"] == "Horst Server"

        role = client.patch(
            f"/api/v1/fleet/nodes/{online_id}/role",
            headers=headers,
            json={"access_role": "beta_tester"},
        )
        assert role.status_code == 200
        assert role.json()["access_role"] == "beta_tester"

        forgotten = client.delete(f"/api/v1/fleet/nodes/{online_id}", headers=headers)
        assert forgotten.status_code == 204
        assert client.get(f"/api/v1/fleet/nodes/{online_id}", headers=headers).status_code == 404

    with database.session() as session:
        assert session.get(Node, online_id) is None
        assert session.query(TelemetryPoint).count() == 0
        assert session.query(AgentToken).count() == 0
        assert session.query(AuditEvent).filter_by(action="node.forgotten").count() == 1
        assert session.query(AuditEvent).filter_by(action="node.renamed").count() == 1
        assert session.query(AuditEvent).filter_by(action="node.access-role.updated").count() == 1


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


def test_monthly_network_usage_uses_counter_deltas_and_handles_resets(tmp_path: Path) -> None:
    database = make_database(tmp_path / "network.db")
    online_id, _ = seed(database)
    now = utc_now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with database.session() as session:
        session.add_all(
            [
                TelemetryPoint(
                    node_id=online_id,
                    sample_id="33333333-3333-4333-8333-333333333333",
                    recorded_at=month_start - timedelta(hours=3),
                    payload={"network": {"bytes_recv": 1000, "bytes_sent": 2000}},
                ),
                TelemetryPoint(
                    node_id=online_id,
                    sample_id="44444444-4444-4444-8444-444444444444",
                    recorded_at=month_start + timedelta(seconds=5),
                    payload={"network": {"bytes_recv": 1300, "bytes_sent": 2400}},
                ),
                TelemetryPoint(
                    node_id=online_id,
                    sample_id="55555555-5555-4555-8555-555555555555",
                    recorded_at=month_start + timedelta(seconds=10),
                    payload={"network": {"bytes_recv": 1500, "bytes_sent": 100}},
                ),
            ]
        )
        session.commit()
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token="dashboard-secret"),
        database,
    )
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/fleet/nodes/{online_id}/network/month",
            headers={"X-NCC-Dashboard-Token": "dashboard-secret"},
        )
    assert response.status_code == 200
    assert response.json()["received_bytes"] == 500
    assert response.json()["sent_bytes"] == 500
    assert response.json()["samples"] == 2


def test_commander_can_reset_visible_network_statistics_without_deleting_raw_data(tmp_path: Path) -> None:
    database = make_database(tmp_path / "network-reset.db")
    online_id, _ = seed(database)
    settings = ServerSettings(database_url="sqlite+pysqlite://", dashboard_token="dashboard-secret")
    app = create_app(settings, database)
    headers = {"X-NCC-Dashboard-Token": "dashboard-secret"}
    with TestClient(app) as client:
        assert client.post("/api/v1/fleet/network/reset", headers=headers).status_code == 204
    reset_time = utc_now()
    with database.session() as session:
        session.add_all(
            [
                TelemetryPoint(
                    node_id=online_id,
                    sample_id="66666666-6666-4666-8666-666666666666",
                    recorded_at=reset_time + timedelta(seconds=5),
                    payload={"network": {"bytes_recv": 1000, "bytes_sent": 2000}},
                ),
                TelemetryPoint(
                    node_id=online_id,
                    sample_id="77777777-7777-4777-8777-777777777777",
                    recorded_at=reset_time + timedelta(seconds=10),
                    payload={"network": {"bytes_recv": 1300, "bytes_sent": 2600}},
                ),
            ]
        )
        session.commit()
    with TestClient(app) as client:
        result = client.get(f"/api/v1/fleet/nodes/{online_id}/network/month", headers=headers)
    assert result.status_code == 200
    assert result.json()["received_bytes"] == 300
    assert result.json()["sent_bytes"] == 600
    with database.session() as session:
        assert session.query(TelemetryPoint).count() == 4
        assert session.query(AuditEvent).filter_by(action="traffic.statistics.reset").count() == 1


def test_monthly_network_usage_ignores_impossible_counter_jumps(tmp_path: Path) -> None:
    database = make_database(tmp_path / "network-sanity.db")
    online_id, _ = seed(database)
    now = utc_now()
    with database.session() as session:
        session.add_all(
            [
                TelemetryPoint(
                    node_id=online_id,
                    sample_id="88888888-8888-4888-8888-888888888888",
                    recorded_at=now - timedelta(seconds=10),
                    payload={"network": {"bytes_recv": 1000, "bytes_sent": 1000}},
                ),
                TelemetryPoint(
                    node_id=online_id,
                    sample_id="99999999-9999-4999-8999-999999999999",
                    recorded_at=now - timedelta(seconds=9),
                    payload={
                        "network": {
                            "bytes_recv": 2 * 1024**3,
                            "bytes_sent": 2 * 1024**3,
                            "download_mbps": 0.01,
                            "upload_mbps": 0.01,
                        }
                    },
                ),
                TelemetryPoint(
                    node_id=online_id,
                    sample_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    recorded_at=now - timedelta(seconds=4),
                    payload={"network": {"bytes_recv": 1600, "bytes_sent": 1300}},
                ),
            ]
        )
        session.commit()
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token="dashboard-secret"),
        database,
    )
    with TestClient(app) as client:
        result = client.get(
            f"/api/v1/fleet/nodes/{online_id}/network/month",
            headers={"X-NCC-Dashboard-Token": "dashboard-secret"},
        )
    assert result.status_code == 200
    assert result.json()["received_bytes"] == 600
    assert result.json()["sent_bytes"] == 300


def test_unraid_polling_uses_a_grace_period() -> None:
    node = Node(
        machine_id="unraid:horsttower",
        display_name="horsttower",
        platform="linux",
        metadata_json={"source": "unraid-api"},
        last_seen_at=utc_now() - timedelta(seconds=45),
    )
    assert is_online(node, 30) is True
