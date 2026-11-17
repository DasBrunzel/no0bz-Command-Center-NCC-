from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base, Node, User
from pydantic import SecretStr

DASHBOARD = {"X-NCC-Dashboard-Token": "dashboard-secret"}


def make_app(tmp_path: Path):  # type: ignore[no-untyped-def]
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'chat.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(
        database_url="sqlite+pysqlite://",
        dashboard_token=SecretStr("dashboard-secret"),
        chat_upload_dir=tmp_path / "uploads",
    )
    return create_app(settings, database), database


def pair(client: TestClient, name: str, suffix: str) -> tuple[dict[str, str], str]:
    identity = {
        "machine_id": f"android-chat-{suffix:0>12}",
        "display_name": name,
        "platform": "android",
        "agent_version": "0.4.0",
        "metadata": {"heartbeat_interval_seconds": 60},
    }
    pairing_id = f"android_chat_pairing_{suffix}"
    pairing = {**identity, "pairing_id": pairing_id, "pairing_secret": "s" * 43}
    assert client.post("/api/v1/agent-pairings/register", json=pairing).status_code == 201
    assert client.post(f"/api/v1/agent-pairings/{pairing_id}/approve", headers=DASHBOARD).status_code == 200
    token = client.post(f"/api/v1/agent-pairings/{pairing_id}/claim", json={"pairing_secret": "s" * 43}).json()["token"]
    agent = {"Authorization": f"Bearer {token}"}
    node_id = client.post("/api/v1/nodes/enroll", json=identity, headers=agent).json()["node_id"]
    return agent, node_id


def test_app_reads_and_writes_the_fleet_chat(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        agent, node_id = pair(client, "Pixel 7 Pro", "1")
        assert client.post("/api/v1/fleet/chat/messages", json={"body": "Hallo vom Dashboard"}, headers=DASHBOARD).status_code == 201

        sent = client.post("/api/v1/nodes/chat/messages", json={"body": "**Hallo** vom Handy", "body_format": "markdown"}, headers=agent)
        assert sent.status_code == 201
        assert sent.json()["sender_node_id"] == node_id
        assert sent.json()["sender_name"] == "Pixel 7 Pro"

        from_app = client.get("/api/v1/nodes/chat/messages", headers=agent).json()
        assert [m["body"] for m in from_app] == ["Hallo vom Dashboard", "**Hallo** vom Handy"]
        # The dashboard sees the phone's message, marked as written by a device.
        from_dashboard = client.get("/api/v1/fleet/chat/messages", headers=DASHBOARD).json()
        assert from_dashboard[-1]["sender_node_id"] == node_id

        newer = client.get(f"/api/v1/nodes/chat/messages?after={from_app[0]['message_id']}", headers=agent).json()
        assert [m["body"] for m in newer] == ["**Hallo** vom Handy"]
        assert client.post("/api/v1/nodes/chat/messages", json={"body": "   "}, headers=agent).status_code == 422
        assert client.get("/api/v1/nodes/chat/participants", headers=agent).status_code == 200


def test_app_uploads_a_photo_and_downloads_attachments(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        agent, node_id = pair(client, "Pixel 7 Pro", "2")
        photo = b"\xff\xd8\xff\xe0" + b"jpeg-bytes" * 50
        uploaded = client.post(
            "/api/v1/nodes/chat/uploads",
            files={"file": ("IMG 2026.jpg", photo, "image/jpeg")},
            data={"body": "Foto vom Serverraum"},
            headers=agent,
        )
        assert uploaded.status_code == 201
        message = uploaded.json()
        assert message["sender_node_id"] == node_id
        assert message["attachment"]["content_type"] == "image/jpeg"
        assert message["attachment"]["size"] == len(photo)

        downloaded = client.get(f"/api/v1/nodes/chat/messages/{message['message_id']}/attachment", headers=agent)
        assert downloaded.status_code == 200
        assert downloaded.content == photo
        assert downloaded.headers["content-type"] == "image/jpeg"
        # The dashboard reaches the same file through its own route.
        assert client.get(message["attachment"]["url"], headers=DASHBOARD).content == photo
        assert client.get("/api/v1/nodes/chat/messages/unknown/attachment", headers=agent).status_code == 404


def test_chat_and_fleet_routes_need_a_valid_agent_token(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer ncc_agent_unknown"}, DASHBOARD):
            assert client.get("/api/v1/nodes/chat/messages", headers=headers).status_code == 401
            assert client.post("/api/v1/nodes/chat/messages", json={"body": "x"}, headers=headers).status_code == 401
            assert client.get("/api/v1/nodes/fleet", headers=headers).status_code == 401


def test_new_messages_reach_connected_apps_live(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        agent, _ = pair(client, "Pixel 7 Pro", "3")
        with client.websocket_connect("/api/v1/nodes/stream", headers=agent) as ws:
            assert ws.receive_json()["type"] == "alert.snapshot"
            client.post("/api/v1/fleet/chat/messages", json={"body": "Ping vom Dashboard"}, headers=DASHBOARD)
            event = ws.receive_json()
            assert event["type"] == "chat.new"
            assert event["message"]["body"] == "Ping vom Dashboard"
            # The phone's own message comes back too, so several devices stay in sync.
            client.post("/api/v1/nodes/chat/messages", json={"body": "Pong"}, headers=agent)
            assert ws.receive_json()["message"]["body"] == "Pong"


def test_commander_phone_lists_every_device_and_a_friends_phone_only_their_own(tmp_path: Path) -> None:
    app, database = make_app(tmp_path)
    with TestClient(app) as client:
        commander_agent, commander_node = pair(client, "Pixel 7 Pro", "4")
        friend_agent, friend_node = pair(client, "Freund-Handy", "5")
        with database.session() as session:
            friend = User(username="freund", role="friend", password_hash="x", active=True)
            session.add(friend)
            session.flush()
            session.add(Node(machine_id="friend-pc-000001", display_name="Freund-PC", platform="windows", approved=True, owner_user_id=friend.id))
            session.add(Node(machine_id="tower-0000000001", display_name="Tower", platform="linux", approved=True))
            session.get(Node, friend_node).owner_user_id = friend.id
            session.commit()

        everything = client.get("/api/v1/nodes/fleet", headers=commander_agent).json()
        assert {n["display_name"] for n in everything} == {"Pixel 7 Pro", "Freund-Handy", "Freund-PC", "Tower"}
        assert next(n for n in everything if n["node_id"] == commander_node)["platform"] == "android"

        own = client.get("/api/v1/nodes/fleet", headers=friend_agent).json()
        assert {n["display_name"] for n in own} == {"Freund-Handy", "Freund-PC"}
        # A friend's phone writes in its owner's name.
        sent = client.post("/api/v1/nodes/chat/messages", json={"body": "Hi"}, headers=friend_agent).json()
        assert sent["sender_name"] == "freund"
