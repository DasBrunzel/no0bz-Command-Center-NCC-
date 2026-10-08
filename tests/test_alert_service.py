from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from ncc_server.alert_service import (
    AlertNotification,
    _track_availability,
    evaluate_alerts,
    mark_notified,
)
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AlertState, AuditEvent, Base, Node, TelemetryPoint, utc_now
from ncc_server.telegram import format_telegram_alert


def test_availability_tracks_total_online_time_and_longest_record() -> None:
    started = utc_now()
    node = Node(machine_id="availability-node", display_name="Availability PC", platform="linux")
    _track_availability(node, True, started)
    _track_availability(node, True, started + timedelta(seconds=30))
    _track_availability(node, False, started + timedelta(seconds=60))

    assert node.availability_started_at == started
    assert node.availability_online_seconds == 30
    assert node.availability_current_streak_seconds == 0
    assert node.availability_record_seconds == 30


def test_telegram_alert_format_is_readable_and_escapes_node_names() -> None:
    rendered = format_telegram_alert(
        AlertNotification(
            "alert-1",
            "active",
            "critical",
            "Tower <1>",
            "offline",
            "Tower <1>: ist offline.",
        ),
        now=utc_now(),
    )
    assert "🔴 <b>NCC KRITISCHE WARNUNG</b>" in rendered
    assert "Tower &lt;1&gt;" in rendered
    assert "Verbindung verloren" in rendered
    assert "ist offline." in rendered


def test_alerts_notify_once_then_send_a_resolution(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'alerts.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(database_url="sqlite+pysqlite://", telegram_enabled=True)
    with database.session() as session:
        node = Node(
            machine_id="alert-node",
            display_name="Alert PC",
            platform="linux",
            approved=True,
            last_seen_at=utc_now(),
        )
        session.add(node)
        session.flush()
        session.add(
            TelemetryPoint(
                node_id=node.id,
                recorded_at=utc_now(),
                payload={"cpu": {"percent": 97.0}},
            )
        )
        session.commit()

    with database.session() as session:
        notifications = evaluate_alerts(session, settings)
        assert len(notifications) == 1
        assert notifications[0].state == "active"
        mark_notified(session, notifications[0].alert_id, "active")

    with database.session() as session:
        assert evaluate_alerts(session, settings) == []
        node = session.query(Node).one()
        session.add(
            TelemetryPoint(
                node_id=node.id,
                recorded_at=utc_now(),
                payload={"cpu": {"percent": 22.0}},
            )
        )
        session.commit()

    with database.session() as session:
        notifications = evaluate_alerts(session, settings)
        assert len(notifications) == 1
        assert notifications[0].state == "resolved"
        assert session.query(AlertState).one().active is False


def test_unraid_temperature_and_array_alerts_are_actionable(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'unraid-alerts.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(database_url="sqlite+pysqlite://")
    with database.session() as session:
        node = Node(machine_id="unraid:test", display_name="Tower", platform="linux", approved=True, last_seen_at=utc_now(), metadata_json={"source": "unraid-api"})
        session.add(node)
        session.flush()
        session.add(TelemetryPoint(node_id=node.id, recorded_at=utc_now(), payload={"cpu": {"temperature_c": 91}, "unraid": {"array_state": "STOPPED"}, "disks": [{"name": "Disk 1", "temperature_c": 56}], "vms": [{"name": "Home Assistant", "state": "CRASHED"}], "containers": [{"name": "Plex", "state": "restarting"}]}))
        session.commit()
    with database.session() as session:
        evaluate_alerts(session, settings)
        kinds = {alert.kind for alert in session.query(AlertState).all()}
    assert {"unraid-array", "cpu-temperature", "disk-temperature-disk 1", "vm-home assistant", "container-plex"} <= kinds


def test_gaming_mode_pauses_only_cpu_and_gpu_load_alerts(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'gaming-alerts.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(database_url="sqlite+pysqlite://")
    with database.session() as session:
        node = Node(
            machine_id="gaming-node",
            display_name="Gaming PC",
            platform="windows",
            approved=True,
            last_seen_at=utc_now(),
            gaming_mode_until=utc_now() + timedelta(hours=2),
        )
        session.add(node)
        session.flush()
        session.add(
            TelemetryPoint(
                node_id=node.id,
                recorded_at=utc_now(),
                payload={
                    "cpu": {"percent": 97.0},
                    "memory": {"percent": 96.0},
                    "gpus": [{"percent": 99.0}],
                },
            )
        )
        session.commit()
    with database.session() as session:
        evaluate_alerts(session, settings)
        kinds = {alert.kind for alert in session.query(AlertState).filter_by(active=True)}
    assert "memory" in kinds
    assert "cpu" not in kinds
    assert "gpu" not in kinds


def test_agent_health_alerts_detect_duplicates_old_version_and_missing_telemetry(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'agent-health.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(database_url="sqlite+pysqlite://", heartbeat_interval_seconds=10)
    with database.session() as session:
        node = Node(
            machine_id="health-node",
            display_name="Health PC",
            platform="windows",
            approved=True,
            agent_version="0.5.0-beta.40",
            last_seen_at=utc_now(),
        )
        session.add(node)
        session.flush()
        session.add(
            TelemetryPoint(
                node_id=node.id,
                recorded_at=utc_now() - timedelta(minutes=2),
                payload={"cpu": {"percent": 10}},
            )
        )
        session.add_all(
            [
                AuditEvent(
                    actor_type="server",
                    actor_id=node.id,
                    action="agent.telemetry.duplicate",
                ),
                AuditEvent(
                    actor_type="server",
                    actor_id=node.id,
                    action="agent.telemetry.duplicate",
                ),
            ]
        )
        session.commit()
    with database.session() as session:
        evaluate_alerts(session, settings)
        kinds = {alert.kind for alert in session.query(AlertState).filter_by(active=True)}
    assert {"agent-no-telemetry", "agent-outdated", "agent-duplicate"} <= kinds


def test_agent_health_alerts_detect_repeated_network_counter_outliers(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'agent-network-health.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(database_url="sqlite+pysqlite://", heartbeat_interval_seconds=10)
    now = utc_now()
    with database.session() as session:
        node = Node(
            machine_id="network-health-node",
            display_name="Network Health PC",
            platform="windows",
            approved=True,
            last_seen_at=now,
        )
        session.add(node)
        session.flush()
        for offset, received in ((-20, 1_000), (-10, 2 * 1024**3), (0, 4 * 1024**3)):
            session.add(
                TelemetryPoint(
                    node_id=node.id,
                    recorded_at=now + timedelta(seconds=offset),
                    payload={
                        "network": {
                            "bytes_recv": received,
                            "bytes_sent": received,
                            "download_mbps": 0.01,
                            "upload_mbps": 0.01,
                        }
                    },
                )
            )
        session.commit()
    with database.session() as session:
        evaluate_alerts(session, settings)
        kinds = {alert.kind for alert in session.query(AlertState).filter_by(active=True)}
    assert "agent-network-outlier" in kinds
