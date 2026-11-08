from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.live_hub import (
    LIVE_TTL_SECONDS,
    VIEWER_TTL_SECONDS,
    AppAlert,
    LiveHub,
    active_app_alerts,
)
from ncc_server.models import AlertState, Base, Node, utc_now
from pydantic import SecretStr
from starlette.websockets import WebSocketDisconnect

DASHBOARD = {"X-NCC-Dashboard-Token": "dashboard-secret"}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def drain(hub_subscriber) -> list[dict]:  # type: ignore[no-untyped-def]
    messages = []
    while not hub_subscriber.queue.empty():
        messages.append(hub_subscriber.queue.get_nowait())
    return messages


def alert(alert_id: str, owner: str | None = None, node: str = "Tower") -> AppAlert:
    return AppAlert(alert_id, f"node-{alert_id}", node, "disk", "warning", f"{node}: Laufwerk voll", "2026-11-08T00:00:00+00:00", owner)


def test_viewer_presence_is_announced_and_expires() -> None:
    clock = FakeClock()
    hub = LiveHub(clock)
    phone = hub.subscribe("phone", commander=True, owner_user_id=None)
    assert drain(phone) == []

    hub.touch_viewer("phone")
    hub.touch_viewer("phone")  # a second poll must not repeat the signal
    assert drain(phone) == [{"type": "viewer.present", "interval_ms": 2000}]

    clock.now += VIEWER_TTL_SECONDS - 1
    hub.expire_viewers()
    assert drain(phone) == []
    clock.now += 2
    hub.expire_viewers()
    assert drain(phone) == [{"type": "viewer.gone"}]


def test_phone_connecting_while_watched_starts_streaming_at_once() -> None:
    hub = LiveHub(FakeClock())
    hub.touch_viewer("phone")
    phone = hub.subscribe("phone", commander=True, owner_user_id=None)
    assert {"type": "viewer.present", "interval_ms": 2000} in drain(phone)


def test_live_point_expires_and_is_dropped_on_disconnect() -> None:
    clock = FakeClock()
    hub = LiveHub(clock)
    phone = hub.subscribe("phone", commander=True, owner_user_id=None)
    hub.store_live("phone", "2026-11-08T12:00:00Z", {"memory": {"percent": 50}})
    assert hub.latest_live("phone").metrics == {"memory": {"percent": 50}}  # type: ignore[union-attr]
    clock.now += LIVE_TTL_SECONDS + 1
    assert hub.latest_live("phone") is None

    hub.store_live("phone", "later", {})
    hub.unsubscribe(phone)
    assert not hub.connected("phone")
    assert hub.latest_live("phone") is None


def test_alerts_are_diffed_and_filtered_by_owner() -> None:
    hub = LiveHub(FakeClock())
    commander = hub.subscribe("phone-a", commander=True, owner_user_id=None)
    friend = hub.subscribe("phone-b", commander=False, owner_user_id="friend-1")

    hub.publish_alerts([alert("a1"), alert("f1", owner="friend-1", node="Freund-PC")], enabled=True)
    assert [m["alert"]["alert_id"] for m in drain(commander)] == ["a1", "f1"]
    friend_messages = drain(friend)
    assert [m["alert"]["alert_id"] for m in friend_messages] == ["f1"]
    assert "owner_user_id" not in friend_messages[0]["alert"]

    # Unchanged alerts are not sent again; a vanished one is reported resolved.
    hub.publish_alerts([alert("f1", owner="friend-1", node="Freund-PC")], enabled=True)
    assert drain(commander) == [{"type": "alert.resolved", "alert": alert("a1").public()}]
    assert drain(friend) == []


def test_disabled_app_alerts_stay_silent_and_resend_snapshot_when_enabled() -> None:
    hub = LiveHub(FakeClock())
    phone = hub.subscribe("phone", commander=True, owner_user_id=None)
    hub.publish_alerts([alert("a1")], enabled=False)
    assert drain(phone) == []
    hub.publish_alerts([alert("a1"), alert("a2")], enabled=True)
    messages = drain(phone)
    assert messages == [{"type": "alert.snapshot", "alerts": [alert("a1").public(), alert("a2").public()]}]


def test_slow_phone_queue_drops_oldest_messages() -> None:
    hub = LiveHub(FakeClock())
    phone = hub.subscribe("phone", commander=True, owner_user_id=None)
    for index in range(250):
        hub.publish_alerts([alert(f"a{index}")], enabled=True)
    assert phone.queue.qsize() == 200


def make_database(path: Path) -> Database:
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    return database


def paired_phone(client: TestClient) -> tuple[dict[str, str], str]:
    identity = {
        "machine_id": "android-live-0000000001",
        "display_name": "Pixel 7 Pro",
        "platform": "android",
        "agent_version": "0.3.0",
        "metadata": {"heartbeat_interval_seconds": 60},
    }
    pairing = {**identity, "pairing_id": "android_live_pairing", "pairing_secret": "s" * 43}
    assert client.post("/api/v1/agent-pairings/register", json=pairing).status_code == 201
    assert client.post("/api/v1/agent-pairings/android_live_pairing/approve", headers=DASHBOARD).status_code == 200
    token = client.post("/api/v1/agent-pairings/android_live_pairing/claim", json={"pairing_secret": "s" * 43}).json()["token"]
    agent = {"Authorization": f"Bearer {token}"}
    node_id = client.post("/api/v1/nodes/enroll", json=identity, headers=agent).json()["node_id"]
    return agent, node_id


def test_stream_delivers_snapshot_live_data_and_viewer_signal(tmp_path: Path) -> None:
    database = make_database(tmp_path / "live.db")
    app = create_app(ServerSettings(database_url="sqlite+pysqlite://", dashboard_token=SecretStr("dashboard-secret")), database)
    with TestClient(app) as client:
        agent, node_id = paired_phone(client)
        with client.websocket_connect("/api/v1/nodes/stream", headers=agent) as ws:
            assert ws.receive_json() == {"type": "alert.snapshot", "alerts": []}

            idle = client.get(f"/api/v1/fleet/nodes/{node_id}/live", headers=DASHBOARD).json()
            assert idle == {"connected": True, "live": False, "recorded_at": None, "metrics": None}
            # The dashboard asking is what makes the phone start streaming.
            assert ws.receive_json() == {"type": "viewer.present", "interval_ms": 2000}

            ws.send_text("kein json")  # ignored, connection stays open
            ws.send_json({"type": "telemetry.live", "recorded_at": "2026-11-08T12:00:00Z", "metrics": {"battery": {"percent": 21}}})
            for _ in range(50):
                live = client.get(f"/api/v1/fleet/nodes/{node_id}/live", headers=DASHBOARD).json()
                if live["live"]:
                    break
            assert live["metrics"] == {"battery": {"percent": 21}}
            assert live["recorded_at"] == "2026-11-08T12:00:00Z"

        after = client.get(f"/api/v1/fleet/nodes/{node_id}/live", headers=DASHBOARD).json()
        assert after["connected"] is False and after["live"] is False


def test_stream_rejects_missing_or_unknown_token(tmp_path: Path) -> None:
    app = create_app(ServerSettings(database_url="sqlite+pysqlite://"), make_database(tmp_path / "reject.db"))
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer ncc_agent_unknown"}):
            with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/v1/nodes/stream", headers=headers) as ws:
                ws.receive_json()


def test_live_endpoint_needs_dashboard_access(tmp_path: Path) -> None:
    app = create_app(ServerSettings(database_url="sqlite+pysqlite://", dashboard_token=SecretStr("dashboard-secret")), make_database(tmp_path / "auth.db"))
    with TestClient(app) as client:
        _, node_id = paired_phone(client)
        assert client.get(f"/api/v1/fleet/nodes/{node_id}/live").status_code == 401
        assert client.get("/api/v1/fleet/nodes/unknown/live", headers=DASHBOARD).status_code == 404


def test_app_alert_switch_is_part_of_the_alert_policy(tmp_path: Path) -> None:
    app = create_app(ServerSettings(database_url="sqlite+pysqlite://", dashboard_token=SecretStr("dashboard-secret")), make_database(tmp_path / "policy.db"))
    with TestClient(app) as client:
        policy = client.get("/api/v1/fleet/alert-policy", headers=DASHBOARD).json()
        assert policy["app_alerts_enabled"] is True
        saved = client.put("/api/v1/fleet/alert-policy", json={**policy, "app_alerts_enabled": False}, headers=DASHBOARD)
        assert saved.status_code == 200
        assert client.get("/api/v1/fleet/alert-policy", headers=DASHBOARD).json()["app_alerts_enabled"] is False


def test_active_app_alerts_reads_open_alerts_with_node_names(tmp_path: Path) -> None:
    database = make_database(tmp_path / "alerts.db")
    with database.session() as session:
        node = Node(machine_id="tower", display_name="Tower", platform="linux", approved=True, last_seen_at=utc_now(), owner_user_id=None)
        session.add(node)
        session.flush()
        session.add_all([
            AlertState(node_id=node.id, kind="disk", severity="critical", message="Tower: Laufwerk bei 97 %"),
            AlertState(node_id=node.id, kind="cpu", severity="warning", message="alt", active=False),
        ])
        session.commit()
        alerts = active_app_alerts(session)
    assert [(a.node_name, a.kind, a.severity) for a in alerts] == [("Tower", "disk", "critical")]
