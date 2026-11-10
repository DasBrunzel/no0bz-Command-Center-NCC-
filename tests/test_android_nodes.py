from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from ncc_server.alert_service import evaluate_alerts
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.fleet_service import default_group_for
from ncc_server.models import AlertState, Base, Node, TelemetryPoint, utc_now
from ncc_server.node_service import is_online
from pydantic import SecretStr


def make_database(path: Path) -> Database:
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    return database


def android_identity() -> dict[str, object]:
    return {
        "machine_id": "android-3f2a9c1e5b7d4f60",
        "display_name": "Pixel 7 Pro",
        "platform": "android",
        "agent_version": "0.2.0",
        "metadata": {"os_release": "17", "soc": "Google Tensor G2", "heartbeat_interval_seconds": 60},
    }


def test_android_app_pairs_enrolls_and_uploads_telemetry(tmp_path: Path) -> None:
    database = make_database(tmp_path / "android.db")
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token=SecretStr("dashboard-secret")),
        database,
    )
    identity = android_identity()
    pairing = {**identity, "pairing_id": "android_pairing_0001", "pairing_secret": "s" * 43}
    with TestClient(app) as client:
        assert client.post("/api/v1/agent-pairings/register", json=pairing).status_code == 201
        assert client.post(
            "/api/v1/agent-pairings/android_pairing_0001/approve",
            headers={"X-NCC-Dashboard-Token": "dashboard-secret"},
        ).status_code == 200
        claimed = client.post(
            "/api/v1/agent-pairings/android_pairing_0001/claim",
            json={"pairing_secret": pairing["pairing_secret"]},
        )
        assert claimed.status_code == 200
        agent = {"Authorization": f"Bearer {claimed.json()['token']}"}

        enrolled = client.post("/api/v1/nodes/enroll", json=identity, headers=agent)
        assert enrolled.status_code == 200
        assert enrolled.json()["platform"] == "android"

        heartbeat = client.post(
            "/api/v1/nodes/heartbeat",
            json={"agent_version": "0.2.0", "metadata": identity["metadata"]},
            headers=agent,
        )
        assert heartbeat.status_code == 200

        point = {
            "sample_id": str(uuid4()),
            "recorded_at": utc_now().isoformat(),
            "metrics": {
                "memory": {"percent": 66.0, "total_gb": 11.2},
                "battery": {"percent": 21, "plugged": True},
                "android": {"soc": "Google Tensor G2", "battery": {"temperature_c": 29.4}},
            },
        }
        uploaded = client.post("/api/v1/nodes/telemetry", json={"points": [point]}, headers=agent)
        assert uploaded.status_code == 200
        assert uploaded.json() == {"accepted": 1, "duplicates": 0}
        # The buffer may resend the same sample after a lost response.
        again = client.post("/api/v1/nodes/telemetry", json={"points": [point]}, headers=agent)
        assert again.json() == {"accepted": 0, "duplicates": 1}


def test_unknown_platform_is_still_rejected(tmp_path: Path) -> None:
    app = create_app(ServerSettings(database_url="sqlite+pysqlite://"), make_database(tmp_path / "p.db"))
    pairing = {**android_identity(), "platform": "ios", "pairing_id": "ios_pairing_000001", "pairing_secret": "s" * 43}
    with TestClient(app) as client:
        assert client.post("/api/v1/agent-pairings/register", json=pairing).status_code == 422


def test_android_node_uses_its_announced_heartbeat_interval() -> None:
    five_minutes_ago = utc_now() - timedelta(minutes=5)
    phone = Node(
        machine_id="android-online",
        display_name="Pixel 7 Pro",
        platform="android",
        last_seen_at=five_minutes_ago,
        metadata_json={"heartbeat_interval_seconds": 300},
    )
    silent = Node(machine_id="android-silent", display_name="Pixel", platform="android", last_seen_at=five_minutes_ago, metadata_json={})
    pc = Node(machine_id="pc", display_name="HorstPC", platform="windows", last_seen_at=five_minutes_ago, metadata_json={"heartbeat_interval_seconds": 300})

    assert is_online(phone, 30)
    assert not is_online(silent, 30)
    # Only Android nodes may stretch the grace period.
    assert not is_online(pc, 30)
    # An absurd announced interval is capped (600 s × 2 + 30 s).
    phone.metadata_json = {"heartbeat_interval_seconds": 100_000}
    phone.last_seen_at = utc_now() - timedelta(minutes=30)
    assert not is_online(phone, 30)


def test_android_machine_id_lands_in_mobile_group() -> None:
    node = Node(machine_id="android-3f2a9c1e5b7d4f60", display_name="Mein Handy", platform="android", metadata_json={})
    assert default_group_for(node) == "default-mobile"


def test_android_node_skips_ram_and_missing_telemetry_alerts(tmp_path: Path) -> None:
    database = make_database(tmp_path / "android-alerts.db")
    settings = ServerSettings(database_url="sqlite+pysqlite://")
    with database.session() as session:
        phone = Node(
            machine_id="android-alerts",
            display_name="Pixel 7 Pro",
            platform="android",
            approved=True,
            last_seen_at=utc_now(),
            metadata_json={"heartbeat_interval_seconds": 60},
        )
        pc = Node(machine_id="pc-alerts", display_name="HorstPC", platform="windows", approved=True, last_seen_at=utc_now())
        session.add_all([phone, pc])
        session.flush()
        old = utc_now() - timedelta(hours=2)
        for node in (phone, pc):
            session.add(
                TelemetryPoint(
                    node_id=node.id,
                    recorded_at=old,
                    payload={"memory": {"percent": 97.0}, "disks": [{"name": "Intern", "percent": 98.0}]},
                )
            )
        session.commit()
        phone_id, pc_id = phone.id, pc.id

    with database.session() as session:
        evaluate_alerts(session, settings)
        kinds = {
            node_id: {alert.kind for alert in session.query(AlertState).filter_by(node_id=node_id, active=True)}
            for node_id in (phone_id, pc_id)
        }
    assert "memory" in kinds[pc_id] and "agent-no-telemetry" in kinds[pc_id]
    assert "memory" not in kinds[phone_id]
    assert "agent-no-telemetry" not in kinds[phone_id]
    # A nearly full phone storage is still worth a warning.
    assert "disk" in kinds[phone_id]
