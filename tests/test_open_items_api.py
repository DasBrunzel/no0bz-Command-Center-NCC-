"""Items DECISIONS.md listed as open after 0.7.0: deleting accounts, agent
invitations with a role, renaming groups, fleet-wide traffic and typed statistics."""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import (
    AuditEvent,
    Base,
    DashboardSession,
    FleetChatMessage,
    Game,
    GameSession,
    HardwareHourly,
    Node,
    TelegramLink,
    TelemetryPoint,
    User,
    utc_now,
)
from pydantic import SecretStr
from sqlalchemy import select

COMMANDER = {"X-NCC-Dashboard-Token": "dashboard-secret"}


def _app(tmp_path: Path):  # type: ignore[no-untyped-def]
    path = tmp_path / "open-items.db"
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(
        database_url=f"sqlite+pysqlite:///{path.as_posix()}", dashboard_token=SecretStr("dashboard-secret"),
        dashboard_allow_loopback_without_token=False, game_metadata_enabled=False,
    )
    return database, create_app(settings, database)


def _user(client: TestClient, username: str, role: str = "friend") -> str:
    created = client.post("/api/v1/users", headers=COMMANDER, json={"username": username, "password": "a long passphrase", "role": role})
    assert created.status_code == 201, created.text
    return str(created.json()["user_id"])


# ── Deleting accounts ─────────────────────────────────────────────────────

def test_commander_deletes_an_account_and_its_sessions(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    with TestClient(app) as commander, TestClient(app) as friend:
        user_id = _user(commander, "kalle")
        assert friend.post("/api/v1/users/login", json={"username": "kalle", "password": "a long passphrase"}).status_code == 200
        assert friend.post("/api/v1/fleet/chat/messages", json={"body": "Moin"}).status_code == 201
        with database.session() as session:
            session.add(TelegramLink(user_id=user_id, chat_id="42"))
            session.commit()

        assert friend.delete(f"/api/v1/users/{user_id}").status_code == 403
        assert commander.delete(f"/api/v1/users/{user_id}", headers=COMMANDER).status_code == 204
        assert commander.delete(f"/api/v1/users/{user_id}", headers=COMMANDER).status_code == 404
        assert friend.get("/api/v1/users/me").status_code == 401
        assert [user["username"] for user in commander.get("/api/v1/users", headers=COMMANDER).json()] == []

    with database.session() as session:
        assert session.get(User, user_id) is None
        assert session.scalars(select(DashboardSession).where(DashboardSession.user_id == user_id)).all() == []
        assert session.scalars(select(TelegramLink)).all() == []
        message = session.scalars(select(FleetChatMessage)).one()
        assert message.sender_user_id is None and message.sender_name == "kalle"
        audit = session.scalars(select(AuditEvent).where(AuditEvent.action == "user.deleted")).one()
        assert "kalle" in (audit.details or "")


def test_deleting_an_account_with_devices_or_the_last_commander_is_refused(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    with TestClient(app) as commander, TestClient(app) as boss:
        friend_id = _user(commander, "kalle")
        with database.session() as session:
            session.add(Node(machine_id="machine-kalle-1", display_name="Kalle-PC", platform="windows", approved=True, owner_user_id=friend_id))
            session.commit()
        refused = commander.delete(f"/api/v1/users/{friend_id}", headers=COMMANDER)
        assert refused.status_code == 409 and "device" in refused.json()["detail"]

        boss_id = _user(commander, "boss", role="commander")
        assert boss.post("/api/v1/users/login", json={"username": "boss", "password": "a long passphrase"}).status_code == 200
        assert boss.delete(f"/api/v1/users/{boss_id}").status_code == 409
        assert commander.delete(f"/api/v1/users/{boss_id}", headers=COMMANDER).status_code == 409


# ── Agent invitations with a role ─────────────────────────────────────────

def test_agent_invitation_carries_its_role_to_the_enrolled_node(tmp_path: Path) -> None:
    _, app = _app(tmp_path)
    with TestClient(app) as client:
        created = client.post("/api/v1/agent-invitations", headers=COMMANDER, json={"name": "Lan-PC", "access_role": "beta_tester"})
        assert created.status_code == 201
        assert created.json()["access_role"] == "beta_tester"
        assert client.get("/api/v1/agent-invitations", headers=COMMANDER).json()[0]["access_role"] == "beta_tester"
        default = client.post("/api/v1/agent-invitations", headers=COMMANDER, json={"name": "Server"})
        assert default.json()["access_role"] == "commander"
        assert client.post("/api/v1/agent-invitations", headers=COMMANDER, json={"name": "x", "access_role": "friend"}).status_code == 422

        enrolled = client.post("/api/v1/nodes/enroll", headers={"Authorization": f"Bearer {created.json()['token']}"}, json={
            "machine_id": f"machine-{uuid.uuid4().hex[:12]}", "display_name": "Lan-PC", "platform": "windows",
            "agent_version": "0.6.2", "metadata": {},
        })
        assert enrolled.status_code in (200, 201), enrolled.text
        node = client.get(f"/api/v1/fleet/nodes/{enrolled.json()['node_id']}", headers=COMMANDER).json()
        assert node["access_role"] == "beta_tester"


# ── Renaming groups ───────────────────────────────────────────────────────

def test_commander_renames_groups_and_names_stay_unique(tmp_path: Path) -> None:
    _, app = _app(tmp_path)
    with TestClient(app) as client:
        groups = {group["group_id"]: group for group in client.get("/api/v1/fleet/groups", headers=COMMANDER).json()}
        assert "default-servers" in groups
        renamed = client.patch("/api/v1/fleet/groups/default-servers", headers=COMMANDER, json={"name": "  Rechenzentrum  "})
        assert renamed.status_code == 200
        assert renamed.json() == {"group_id": "default-servers", "name": "Rechenzentrum", "position": groups["default-servers"]["position"]}
        assert {group["name"] for group in client.get("/api/v1/fleet/groups", headers=COMMANDER).json()} >= {"Rechenzentrum"}
        assert client.patch("/api/v1/fleet/groups/default-mobile", headers=COMMANDER, json={"name": "rechenzentrum"}).status_code == 409
        assert client.patch("/api/v1/fleet/groups/default-servers", headers=COMMANDER, json={"name": "Rechenzentrum"}).status_code == 200
        assert client.patch("/api/v1/fleet/groups/missing", headers=COMMANDER, json={"name": "Neu"}).status_code == 404
        assert client.patch("/api/v1/fleet/groups/default-mobile", headers=COMMANDER, json={"name": "   "}).status_code == 422


# ── Fleet-wide traffic ────────────────────────────────────────────────────

def test_fleet_network_sums_online_nodes_and_buckets_history(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    now = utc_now()
    with database.session() as session:
        first = Node(machine_id="machine-net-1", display_name="Alpha", platform="windows", approved=True, last_seen_at=now)
        second = Node(machine_id="machine-net-2", display_name="Beta", platform="linux", approved=True, last_seen_at=now)
        gone = Node(machine_id="machine-net-3", display_name="Gamma", platform="linux", approved=True, last_seen_at=now - timedelta(hours=1))
        session.add_all([first, second, gone])
        session.flush()
        for offset, down in ((65, 10.0), (60, 30.0), (5, 40.0)):
            session.add(TelemetryPoint(node_id=first.id, sample_id=str(uuid.uuid4()), recorded_at=now - timedelta(seconds=offset),
                                       payload={"network": {"download_mbps": down, "upload_mbps": 1.0}, "cpu": {"percent": 5}}))
        session.add(TelemetryPoint(node_id=second.id, sample_id=str(uuid.uuid4()), recorded_at=now - timedelta(seconds=4),
                                   payload={"network": {"download_mbps": 2.5, "upload_mbps": 0.5}}))
        session.add(TelemetryPoint(node_id=second.id, sample_id=str(uuid.uuid4()), recorded_at=now - timedelta(seconds=3),
                                   payload={"cpu": {"percent": 5}}))
        session.add(TelemetryPoint(node_id=gone.id, sample_id=str(uuid.uuid4()), recorded_at=now - timedelta(hours=2),
                                   payload={"network": {"download_mbps": 999.0, "upload_mbps": 999.0}}))
        session.commit()

    with TestClient(app) as client:
        assert client.get("/api/v1/fleet/network").status_code == 401
        body = client.get("/api/v1/fleet/network?minutes=10", headers=COMMANDER).json()
        assert body["minutes"] == 10 and body["bucket_seconds"] == 10
        assert body["online_nodes"] == 2
        assert body["download_mbps"] == 42.5 and body["upload_mbps"] == 1.5
        assert [node["display_name"] for node in body["nodes"]] == ["Alpha", "Beta"]
        # 65 s and 60 s ago share a 10-second bucket; Alpha's readings are averaged, not added.
        downloads = [sample["download_mbps"] for sample in body["history"]]
        assert 20.0 in downloads and downloads[-1] == 42.5
        assert body["history"][-1]["nodes"] == 2
        assert client.get("/api/v1/fleet/network?minutes=0", headers=COMMANDER).status_code == 422


def test_friends_only_see_their_own_traffic(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    with TestClient(app) as commander, TestClient(app) as friend:
        friend_id = _user(commander, "kalle")
        now = utc_now()
        with database.session() as session:
            own = Node(machine_id="machine-own-1", display_name="Kalle-PC", platform="windows", approved=True, last_seen_at=now, owner_user_id=friend_id)
            other = Node(machine_id="machine-other-1", display_name="Server", platform="linux", approved=True, last_seen_at=now)
            session.add_all([own, other])
            session.flush()
            for node, down in ((own, 3.0), (other, 50.0)):
                session.add(TelemetryPoint(node_id=node.id, sample_id=str(uuid.uuid4()), recorded_at=now,
                                           payload={"network": {"download_mbps": down, "upload_mbps": 0.0}}))
            session.commit()
        assert friend.post("/api/v1/users/login", json={"username": "kalle", "password": "a long passphrase"}).status_code == 200
        body = friend.get("/api/v1/fleet/network").json()
        assert body["download_mbps"] == 3.0
        assert [node["display_name"] for node in body["nodes"]] == ["Kalle-PC"]


# ── Typed statistics ──────────────────────────────────────────────────────

def test_statistics_endpoints_publish_their_schema(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    now = utc_now().replace(minute=0, second=0, microsecond=0)
    with database.session() as session:
        node = Node(machine_id="machine-stats-1", display_name="HorstPC", platform="windows", approved=True, last_seen_at=now)
        game = Game(key="steam:factorio", title="Factorio", launcher="steam")
        session.add_all([node, game])
        session.flush()
        session.add(GameSession(node_id=node.id, game_id=game.id, started_at=now - timedelta(hours=3), ended_at=now - timedelta(hours=1),
                                hardware={"cpu_percent": [100.0, 2.0, 70.0], "energy_wh": [12.0, 1.0, 12.0]}))
        session.add(HardwareHourly(node_id=node.id, hour=now - timedelta(hours=2), sample_count=2,
                                   values={"cpu_percent": [60.0, 2.0, 45.0]}, energy_wh=20.0))
        session.commit()

    with TestClient(app) as client:
        schema = app.openapi()
        responses = schema["paths"]["/api/v1/fleet/games/stats"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert responses["$ref"].endswith("PlaytimeStatisticsResponse")
        hardware = schema["paths"]["/api/v1/fleet/hardware/stats"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert hardware["$ref"].endswith("HardwareStatisticsResponse")

        games = client.get("/api/v1/fleet/games/stats?days=0", headers=COMMANDER).json()
        assert games["total_seconds"] == 7200 and games["game_count"] == 1
        assert games["games"][0]["hardware"]["cpu_percent"] == {"average": 50.0, "max": 70.0}
        assert games["games"][0]["energy_wh"] == 12.0
        assert len(games["heatmap"]) == 7 and len(games["heatmap"][0]) == 24
        assert games["longest_session"]["title"] == "Factorio"

        stats = client.get("/api/v1/fleet/hardware/stats?days=0", headers=COMMANDER).json()
        assert stats["summary"]["cpu_percent"] == {"average": 30.0, "max": 45.0}
        assert stats["records"]["cpu_percent"]["node_name"] == "HorstPC"
        assert stats["energy_wh"] == 20.0 and stats["hours_covered"] == 1
