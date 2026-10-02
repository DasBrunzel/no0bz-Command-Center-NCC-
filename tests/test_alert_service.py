from __future__ import annotations

from pathlib import Path

from ncc_server.alert_service import evaluate_alerts, mark_notified
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AlertState, Base, Node, TelemetryPoint, utc_now


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
