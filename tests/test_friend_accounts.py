"""Friend accounts must only ever see and change their own devices."""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.agent_tokens import issue_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base, Node, utc_now
from pydantic import SecretStr

COMMANDER = {"X-NCC-Dashboard-Token": "dashboard-secret"}
PASSWORD = "friend-password-123"


def _app(tmp_path: Path):  # type: ignore[no-untyped-def]
    path = tmp_path / "ncc-friends.db"
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(
        database_url=f"sqlite+pysqlite:///{path.as_posix()}", dashboard_token=SecretStr("dashboard-secret"),
        dashboard_allow_loopback_without_token=False, game_metadata_enabled=False,
    )
    return database, create_app(settings, database)


def _commander_node(database: Database, client: TestClient, machine_id: str = "machine-commander-1") -> tuple[str, dict[str, str]]:
    with database.session() as session:
        token = issue_agent_token(session, "HorstPC", utc_now() + timedelta(hours=1)).plaintext
    agent = {"Authorization": f"Bearer {token}"}
    node_id = client.post("/api/v1/nodes/enroll", headers=agent, json={
        "machine_id": machine_id, "display_name": "HorstPC", "platform": "windows", "agent_version": "0.6.0", "metadata": {},
    }).json()["node_id"]
    return node_id, agent


def _register_friend(app, commander: TestClient, username: str = "kumpel") -> TestClient:  # type: ignore[no-untyped-def]
    code = commander.post("/api/v1/users/invites", headers=COMMANDER, json={"label": username}).json()["code"]
    friend = TestClient(app)
    response = friend.post("/api/v1/users/register", json={"code": code.lower().replace("-", " "), "username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return friend


def _pair(client: TestClient, approver: TestClient, approver_headers: dict[str, str], machine_id: str) -> tuple[int, dict[str, str] | None]:
    pairing_id = f"pairing_{uuid.uuid4().hex[:16]}"
    secret = uuid.uuid4().hex * 2
    client.post("/api/v1/agent-pairings/register", json={
        "pairing_id": pairing_id, "pairing_secret": secret, "machine_id": machine_id,
        "display_name": "Freund-PC", "platform": "windows", "agent_version": "0.6.0", "metadata": {},
    })
    approved = approver.post(f"/api/v1/agent-pairings/{pairing_id}/approve", headers=approver_headers)
    if approved.status_code != 200:
        return approved.status_code, None
    token = client.post(f"/api/v1/agent-pairings/{pairing_id}/claim", json={"pairing_secret": secret}).json()["token"]
    return 200, {"Authorization": f"Bearer {token}"}


def test_invite_code_creates_one_friend_account(tmp_path: Path) -> None:
    _, app = _app(tmp_path)
    with TestClient(app) as commander:
        created = commander.post("/api/v1/users/invites", headers=COMMANDER, json={"label": "Max"})
        assert created.status_code == 201
        code = created.json()["code"]
        assert len(code) == 14 and created.json()["status"] == "open"
        anonymous = TestClient(app)
        assert anonymous.post("/api/v1/users/invites", json={"label": "x"}).status_code in {401, 403}
        assert anonymous.post("/api/v1/users/register", json={"code": "WRONG-CODE-1234", "username": "max", "password": PASSWORD}).status_code == 403
        assert anonymous.post("/api/v1/users/register", json={"code": code, "username": "max", "password": PASSWORD}).status_code == 201
        me = anonymous.get("/api/v1/users/me").json()
        assert me["role"] == "friend" and me["username"] == "max"
        # A code works exactly once.
        assert TestClient(app).post("/api/v1/users/register", json={"code": code, "username": "max2", "password": PASSWORD}).status_code == 403
        invites = commander.get("/api/v1/users/invites", headers=COMMANDER).json()
        assert invites[0]["status"] == "used" and invites[0]["used_by"] == "max"
        assert anonymous.get("/api/v1/users/invites").status_code == 403


def test_friend_sees_and_changes_only_own_devices(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    with TestClient(app) as commander:
        horst_id, horst_agent = _commander_node(database, commander)
        commander.post("/api/v1/nodes/telemetry", headers=horst_agent, json={"points": [
            {"sample_id": str(uuid.uuid4()), "recorded_at": utc_now().isoformat(), "metrics": {"cpu": {"percent": 50, "temperature_c": 60}}},
        ]})
        friend = _register_friend(app, commander)

        # Nothing of the commander's leaks to the friend.
        assert friend.get("/api/v1/fleet/nodes").json() == []
        assert friend.get("/api/v1/fleet/summary").json()["total_nodes"] == 0
        for path in (f"/api/v1/fleet/nodes/{horst_id}", f"/api/v1/fleet/nodes/{horst_id}/telemetry",
                     f"/api/v1/fleet/nodes/{horst_id}/network/history", f"/api/v1/fleet/nodes/{horst_id}/network/month"):
            assert friend.get(path).status_code == 404, path
        assert friend.get("/api/v1/fleet/hardware/stats", params={"node_id": horst_id}).status_code == 404
        assert friend.get("/api/v1/fleet/hardware/stats").json()["hours_covered"] == 0
        assert friend.patch(f"/api/v1/fleet/nodes/{horst_id}", json={"display_name": "Mine"}).status_code == 404
        assert friend.put(f"/api/v1/fleet/nodes/{horst_id}/gaming-mode", json={"minutes": 60}).status_code == 404
        for method, path in (("get", "/api/v1/agent-pairings"), ("get", "/api/v1/admin-codes"), ("get", "/api/v1/releases"),
                             ("get", "/api/v1/agent-invitations"), ("get", "/api/v1/fleet/telegram"), ("get", "/api/v1/users"),
                             ("put", "/api/v1/fleet/layout"), ("post", "/api/v1/fleet/groups")):
            body = {"placements": []} if method == "put" else {"name": "x"} if method == "post" else None
            response = friend.request(method.upper(), path, json=body)
            assert response.status_code == 403, path
        assert friend.put("/api/v1/fleet/alert-policy", json={"cpu_threshold": 90, "memory_threshold": 90, "gpu_threshold": 90, "disk_threshold": 90}).status_code == 403

        # The friend pairs a PC and owns it.
        status, friend_agent = _pair(commander, friend, {}, "machine-friend-1")
        assert status == 200 and friend_agent is not None
        friend_node = commander.post("/api/v1/nodes/enroll", headers=friend_agent, json={
            "machine_id": "machine-friend-1", "display_name": "Freund-PC", "platform": "windows", "agent_version": "0.6.0", "metadata": {},
        }).json()["node_id"]
        own = friend.get("/api/v1/fleet/nodes").json()
        assert [node["node_id"] for node in own] == [friend_node]
        assert own[0]["owner_name"] == "kumpel" and own[0]["fleet_group_id"] == "default-friends"
        assert friend.patch(f"/api/v1/fleet/nodes/{friend_node}", json={"display_name": "Gaming-Kiste"}).status_code == 200
        assert friend.put(f"/api/v1/fleet/nodes/{friend_node}/gaming-mode", json={"minutes": 60}).status_code == 200
        assert friend.put(f"/api/v1/fleet/nodes/{friend_node}/sensor-labels", json={"key": "fan:Fan #1", "name": "CPU"}).status_code == 200
        # Server-wide actions stay with the commander, even on own devices.
        assert friend.delete(f"/api/v1/fleet/nodes/{friend_node}").status_code == 403
        assert friend.put(f"/api/v1/fleet/nodes/{friend_node}/release", json={"release_id": None}).status_code == 403
        # The commander still sees everything, with the owner.
        everything = {node["node_id"]: node for node in commander.get("/api/v1/fleet/nodes", headers=COMMANDER).json()}
        assert set(everything) == {horst_id, friend_node}
        assert everything[friend_node]["owner_name"] == "kumpel"


def test_friend_cannot_take_over_an_existing_device_by_its_machine_id(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    with TestClient(app) as commander:
        _, _ = _commander_node(database, commander, "machine-commander-1")
        friend = _register_friend(app, commander)
        status, agent = _pair(commander, friend, {}, "machine-commander-1")
        assert status == 403 and agent is None
        with database.session() as session:
            node = session.query(Node).filter_by(machine_id="machine-commander-1").one()
            assert node.owner_user_id is None


def test_commander_grants_full_statistics_and_assigns_owners(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    with TestClient(app) as commander:
        horst_id, horst_agent = _commander_node(database, commander)
        game = {"title": "Brotato", "launcher": "steam", "app_id": "1942280"}
        now = utc_now()
        commander.post("/api/v1/nodes/telemetry", headers=horst_agent, json={"points": [
            {"sample_id": str(uuid.uuid4()), "recorded_at": (now - timedelta(seconds=10 - 10 * index)).isoformat(), "metrics": {"cpu": {"percent": 50}, "game": game}}
            for index in range(2)
        ]})
        friend = _register_friend(app, commander)
        assert friend.get("/api/v1/fleet/games/stats").json()["total_seconds"] == 0
        assert friend.get("/api/v1/fleet/games").json() == []

        user_id = friend.get("/api/v1/users/me").json()["user_id"]
        assert commander.patch(f"/api/v1/users/{user_id}", headers=COMMANDER, json={"full_statistics": True}).json()["full_statistics"] is True
        assert friend.get("/api/v1/fleet/games/stats").json()["total_seconds"] == 10
        assert friend.get("/api/v1/fleet/hardware/stats", params={"node_id": horst_id}).status_code == 200
        assert [game["title"] for game in friend.get("/api/v1/fleet/games").json()] == ["Brotato"]
        # Statistics access does not reveal the device itself.
        assert friend.get("/api/v1/fleet/nodes").json() == []
        assert friend.get(f"/api/v1/fleet/nodes/{horst_id}").status_code == 404

        assert friend.put(f"/api/v1/fleet/nodes/{horst_id}/owner", json={"user_id": user_id}).status_code == 403
        assert commander.put(f"/api/v1/fleet/nodes/{horst_id}/owner", headers=COMMANDER, json={"user_id": "unknown"}).status_code == 422
        assigned = commander.put(f"/api/v1/fleet/nodes/{horst_id}/owner", headers=COMMANDER, json={"user_id": user_id}).json()
        assert assigned["owner_name"] == "kumpel"
        assert [node["node_id"] for node in friend.get("/api/v1/fleet/nodes").json()] == [horst_id]
        users = {user["username"]: user for user in commander.get("/api/v1/users", headers=COMMANDER).json()}
        assert users["kumpel"]["device_count"] == 1


def test_chat_attachments_from_others_never_render_as_html(tmp_path: Path) -> None:
    _, app = _app(tmp_path)
    upload_dir = tmp_path / "uploads"
    app.state.server_settings.chat_upload_dir = upload_dir
    with TestClient(app) as commander:
        friend = _register_friend(app, commander)
        html = friend.post("/api/v1/fleet/chat/uploads", files={"file": ("x.html", b"<script>alert(1)</script>", "text/html")}).json()
        image = friend.post("/api/v1/fleet/chat/uploads", files={"file": ("x.png", b"\x89PNG", "image/png")}).json()
        served = commander.get(f"/api/v1/fleet/chat/messages/{html['message_id']}/attachment", headers=COMMANDER)
        assert served.headers["content-type"] == "application/octet-stream"
        assert served.headers["content-disposition"].startswith("attachment")
        assert commander.get(f"/api/v1/fleet/chat/messages/{image['message_id']}/attachment", headers=COMMANDER).headers["content-type"] == "image/png"
