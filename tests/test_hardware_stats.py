from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.agent_tokens import issue_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.hardware_metrics import hardware_values
from ncc_server.hardware_stats import backfill_step, hardware_statistics
from ncc_server.models import Base, HardwareHourly, Node, TelemetryPoint, utc_now
from pydantic import SecretStr
from sqlalchemy import select

DASHBOARD = {"X-NCC-Dashboard-Token": "dashboard-secret"}


def _metrics(cpu_temp: float, cpu_power: float = 40.0, gpu_power: float = 140.0) -> dict[str, object]:
    return {
        "cpu": {"percent": 30.0, "temperature_c": cpu_temp, "power_w": cpu_power},
        "memory": {"percent": 40.0},
        "gpus": [{"percent": 90.0, "temperature_c": 70.0}],
        "lhm_gpus": [{"temperature_c": 71.0, "hotspot_temperature_c": 82.0, "power_w": gpu_power}],
        "hardware": {
            "memory_modules": [{"temperature_c": 38.0}, {"temperature_c": 41.5}],
            "storage": [{"temperature_c": 36.0}, {"temperature_c": 44.0}],
            "board": {"fans": [{"label": "Fan #2", "rpm": 1100}, {"label": "Fan #3", "rpm": 900}]},
        },
    }


def test_hardware_values_pick_hottest_parts_and_named_fans() -> None:
    values = hardware_values(_metrics(60), {"fan:Fan #2": {"name": "CPU", "role": "cpu"}})
    assert values["ram_temperature_c"] == 41.5
    assert values["drive_temperature_c"] == 44.0
    assert values["gpu_temperature_c"] == 71.0 and values["gpu_hotspot_c"] == 82.0
    assert values["cpu_fan_rpm"] == 1100
    # A fan without a role is not part of the statistics.
    assert "case_fan_rpm" not in values


def _setup(tmp_path: Path) -> tuple[Database, TestClient, dict[str, str], str]:
    path = tmp_path / "ncc-hardware.db"
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        plaintext = issue_agent_token(session, "PC", utc_now() + timedelta(hours=1)).plaintext
    settings = ServerSettings(database_url=f"sqlite+pysqlite:///{path.as_posix()}", dashboard_token=SecretStr("dashboard-secret"), game_metadata_enabled=False)
    client = TestClient(create_app(settings, database))
    agent = {"Authorization": f"Bearer {plaintext}"}
    node_id = client.post("/api/v1/nodes/enroll", headers=agent, json={
        "machine_id": "machine-hardware-1", "display_name": "Gaming PC", "platform": "windows", "agent_version": "0.6.0", "metadata": {},
    }).json()["node_id"]
    return database, client, agent, node_id


def _point(at: datetime, metrics: dict[str, object]) -> dict[str, object]:
    return {"sample_id": str(uuid.uuid4()), "recorded_at": at.isoformat(), "metrics": metrics}


def test_live_points_build_hourly_rows_with_energy(tmp_path: Path) -> None:
    database, client, agent, node_id = _setup(tmp_path)
    start = utc_now().replace(minute=10, second=0, microsecond=0) - timedelta(hours=1)
    with client:
        # Four points 10 s apart at 180 W, then one after a 5-minute pause.
        points = [_point(start + timedelta(seconds=10 * index), _metrics(60 + index)) for index in range(4)]
        points.append(_point(start + timedelta(minutes=5), _metrics(50)))
        client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": points})
        stats = client.get("/api/v1/fleet/hardware/stats", headers=DASHBOARD, params={"days": 7, "node_id": node_id}).json()
    with database.session() as session:
        row = session.scalar(select(HardwareHourly))
        assert row is not None and row.sample_count == 5
        # Three 10-second intervals count; the pause does not.
        assert round(row.energy_wh, 3) == round(180 * 30 / 3600, 3)
    assert stats["records"]["cpu_temperature_c"]["value"] == 63.0
    assert stats["summary"]["cpu_temperature_c"] == {"average": 59.2, "max": 63.0}
    assert stats["energy_wh"] == 1.5
    assert "cpu_temperature_c" in stats["metrics"] and stats["daily"]


def test_backfill_adds_stored_history_once(tmp_path: Path) -> None:
    database, client, agent, node_id = _setup(tmp_path)
    old = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    with database.session() as session:
        for index in range(5):
            session.add(TelemetryPoint(node_id=node_id, sample_id=str(uuid.uuid4()), recorded_at=old + timedelta(seconds=10 * index), payload=_metrics(70 + index)))
        session.commit()
    with client:
        client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": [_point(utc_now(), _metrics(55))]})
    with database.session() as session:
        node = session.get(Node, node_id)
        assert node is not None
        # The live point is already counted; the backfill must skip it.
        assert backfill_step(session, node, batch=3) == 3
        assert backfill_step(session, node, batch=3) == 2
        assert node.rollup_backfill_done is True
        assert backfill_step(session, node, batch=3) == 0
        stats = hardware_statistics(session, days=0, node_id=node_id, utc_offset_minutes=0)
    assert stats["records"]["cpu_temperature_c"]["value"] == 74.0
    assert stats["summary"]["cpu_temperature_c"]["max"] == 74.0
    assert sum(day["metrics"]["cpu_temperature_c"]["max"] > 0 for day in stats["daily"]) == 2
    # Energy across the batch boundary: four 10-second intervals at 180 W.
    assert round(sum(day["energy_wh"] for day in stats["daily"] if day["date"] == "2026-10-01"), 2) == 2.0


def test_game_sessions_record_energy(tmp_path: Path) -> None:
    _, client, agent, _ = _setup(tmp_path)
    now = utc_now()
    game = {"title": "Cyberpunk 2077", "launcher": "steam", "app_id": "1091500"}
    with client:
        points = []
        for index in range(3):
            metrics = _metrics(60)
            metrics["game"] = game
            points.append(_point(now - timedelta(seconds=20 - 10 * index), metrics))
        client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": points})
        top = client.get("/api/v1/fleet/games/stats", headers=DASHBOARD, params={"days": 7}).json()["games"][0]
    assert top["energy_wh"] == 1.0
    assert top["hardware"]["gpu_hotspot_c"] == {"average": 82.0, "max": 82.0}
    assert "energy_wh" not in top["hardware"]
