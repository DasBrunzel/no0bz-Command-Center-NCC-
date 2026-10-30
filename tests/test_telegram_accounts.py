from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from ncc_server import app as app_module
from ncc_server import telegram_bot
from ncc_server.agent_tokens import issue_agent_token
from ncc_server.alert_service import AlertNotification, evaluate_alerts
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AlertState, Base, Node, TelegramLink, User, utc_now
from ncc_server.telegram_bot import (
    alert_recipients,
    poll_updates,
    send_weekly_recaps,
    weekly_recap_due,
)
from ncc_server.user_passwords import hash_password
from pydantic import SecretStr

COMMANDER = {"X-NCC-Dashboard-Token": "dashboard-secret"}


@pytest.fixture(autouse=True)
def offline_telegram(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may reach api.telegram.org."""
    async def idle(*_: object) -> None:
        return None

    monkeypatch.setattr(app_module, "_telegram_bot_loop", idle)
    monkeypatch.setattr(telegram_bot, "_bot_username", "ncc_test_bot")


def _settings(path: Path, **values: Any) -> ServerSettings:
    return ServerSettings(
        database_url=f"sqlite+pysqlite:///{path.as_posix()}", dashboard_token=SecretStr("dashboard-secret"),
        dashboard_allow_loopback_without_token=False, game_metadata_enabled=False,
        telegram_enabled=True, telegram_bot_token=SecretStr("123:test"), telegram_chat_id="owner-chat", **values,
    )


def _database(tmp_path: Path) -> tuple[Database, Path]:
    path = tmp_path / "ncc-telegram.db"
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    return database, path


class FakeTelegram:
    def __init__(self, updates: list[dict[str, Any]] | None = None) -> None:
        self.updates = updates or []
        self.sent: list[tuple[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getUpdates"):
            offset = int(request.url.params["offset"])
            return httpx.Response(200, json={"ok": True, "result": [update for update in self.updates if update["update_id"] >= offset]})
        if request.url.path.endswith("/sendMessage"):
            body = json.loads(request.content)
            self.sent.append((str(body["chat_id"]), body["text"]))
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


def test_temperatures_alert_also_in_gaming_mode(tmp_path: Path) -> None:
    database, path = _database(tmp_path)
    settings = _settings(path)
    with database.session() as session:
        node = Node(machine_id="hot-pc", display_name="Hot PC", platform="windows", approved=True, last_seen_at=utc_now(),
                    gaming_mode_until=utc_now() + timedelta(hours=1))
        session.add(node)
        session.flush()
        from ncc_server.models import TelemetryPoint
        session.add(TelemetryPoint(node_id=node.id, recorded_at=utc_now(), payload={
            "cpu": {"percent": 99.0, "temperature_c": 95.0},
            "lhm_gpus": [{"temperature_c": 86.0}],
            "hardware": {"storage": [{"name": "Samsung SSD", "temperature_c": 71.0}, {"name": "Cool SSD", "temperature_c": 40.0}]},
        }))
        session.commit()
        evaluate_alerts(session, settings)
        alerts = {state.kind: state.severity for state in session.query(AlertState).filter_by(active=True)}
    # CPU load is silenced while gaming, heat is not.
    assert alerts == {"cpu-temperature": "critical", "gpu-temperature": "warning", "drive-temperature-samsung ssd": "critical"}


def test_dashboard_link_code_and_bot_message_link_a_friend(tmp_path: Path) -> None:
    database, path = _database(tmp_path)
    with database.session() as session:
        session.add(User(username="max", password_hash=hash_password("friend-password-1"), role="friend", active=True))
        session.commit()
    client = TestClient(app_module.create_app(_settings(path), database))
    with client:
        assert client.post("/api/v1/users/login", json={"username": "max", "password": "friend-password-1"}).status_code == 200
        status = client.get("/api/v1/users/me/telegram").json()
        assert status == {"available": True, "linked": False, "telegram_name": None, "weekly_recap": True, "bot_username": "ncc_test_bot"}
        issued = client.post("/api/v1/users/me/telegram/link").json()
        assert issued["deep_link"] == f"https://t.me/ncc_test_bot?start={issued['code']}"
        # The dashboard token has no personal account to link.
        assert TestClient(client.app).post("/api/v1/users/me/telegram/link", headers=COMMANDER).status_code == 403

        fake = FakeTelegram([
            {"update_id": 10, "message": {"chat": {"id": 555, "type": "group"}, "from": {"username": "max"}, "text": f"/start {issued['code']}"}},
            {"update_id": 11, "message": {"chat": {"id": 777, "type": "private"}, "from": {"username": "max"}, "text": "/start WRONGCODE1"}},
            {"update_id": 12, "message": {"chat": {"id": 777, "type": "private"}, "from": {"username": "max"}, "text": f"/start {issued['code']}"}},
        ])
        assert asyncio.run(poll_updates(database, _settings(path), fake.transport, timeout=0)) == 3
        # Groups are ignored; a wrong code gets a hint; the right one links.
        assert [chat for chat, _ in fake.sent] == ["777", "777"]
        assert "ungültig" in fake.sent[0][1] and "Verbunden" in fake.sent[1][1]
        # Updates are consumed once.
        assert asyncio.run(poll_updates(database, _settings(path), fake.transport, timeout=0)) == 0

        linked = client.get("/api/v1/users/me/telegram").json()
        assert linked["linked"] is True and linked["telegram_name"] == "@max"
        assert client.patch("/api/v1/users/me/telegram", json={"weekly_recap": False}).json()["weekly_recap"] is False
        assert client.delete("/api/v1/users/me/telegram").status_code == 204
        assert client.get("/api/v1/users/me/telegram").json()["linked"] is False


def test_alerts_reach_the_owner_and_never_other_friends(tmp_path: Path) -> None:
    database, path = _database(tmp_path)
    settings = _settings(path)
    with database.session() as session:
        max_user = User(username="max", password_hash="x", role="friend", active=True)
        tim = User(username="tim", password_hash="x", role="friend", active=True)
        boss = User(username="boss", password_hash="x", role="commander", active=True)
        session.add_all([max_user, tim, boss])
        session.flush()
        session.add_all([
            TelegramLink(user_id=max_user.id, chat_id="max-chat"), TelegramLink(user_id=tim.id, chat_id="tim-chat"),
            # The commander's own link is the owner chat; it must not double up.
            TelegramLink(user_id=boss.id, chat_id="owner-chat"),
        ])
        session.commit()
        for_max = AlertNotification("a1", "active", "warning", "MAX-PC", "cpu-temperature", "heiß", "node-1", max_user.id)
        for_owner = AlertNotification("a2", "active", "warning", "HorstPC", "cpu-temperature", "heiß", "node-2", None)
        assert alert_recipients(session, settings, for_max) == ["owner-chat", "max-chat"]
        assert alert_recipients(session, settings, for_owner) == ["owner-chat"]


def test_weekly_recap_once_per_week_from_monday_morning() -> None:
    berlin = timezone(timedelta(hours=1))
    monday = datetime(2026, 11, 2, 8, 59, tzinfo=berlin)
    assert weekly_recap_due(monday, None) is None
    assert weekly_recap_due(monday + timedelta(minutes=1), None) == "2026-W45"
    assert weekly_recap_due(monday + timedelta(hours=3), "2026-W45") is None
    # A server that was off on Monday catches up later that week.
    assert weekly_recap_due(monday + timedelta(days=2), "2026-W44") == "2026-W45"


def test_weekly_recap_goes_to_each_chat_with_its_own_devices(tmp_path: Path) -> None:
    database, path = _database(tmp_path)
    settings = _settings(path)
    client = TestClient(app_module.create_app(settings, database))
    with database.session() as session:
        friend = User(username="max", password_hash="x", role="friend", active=True)
        session.add(friend)
        session.flush()
        session.add(TelegramLink(user_id=friend.id, chat_id="max-chat"))
        session.commit()
        friend_id = friend.id
    now = utc_now()
    with client:
        for name, game, app_id, owner in (("HorstPC", "Brotato", "1942280", None), ("MAX-PC", "DayZ", "221100", friend_id)):
            with database.session() as session:
                token = issue_agent_token(session, name, now + timedelta(hours=1))
                token.record.owner_user_id = owner
                session.commit()
                plaintext = token.plaintext
            agent = {"Authorization": f"Bearer {plaintext}"}
            client.post("/api/v1/nodes/enroll", headers=agent, json={"machine_id": f"m-{name}", "display_name": name, "platform": "windows", "agent_version": "0.6.0", "metadata": {}})
            client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": [
                {"sample_id": str(uuid.uuid4()), "recorded_at": (now - timedelta(seconds=20 - 10 * step)).isoformat(),
                 "metrics": {"cpu": {"percent": 50, "temperature_c": 70 + step}, "game": {"title": game, "launcher": "steam", "app_id": app_id}}}
                for step in range(3)
            ]})
    fake = FakeTelegram()
    monday = datetime.now().astimezone()
    monday = monday - timedelta(days=monday.weekday())
    monday = monday.replace(hour=10)
    assert asyncio.run(send_weekly_recaps(database, settings, monday, fake.transport)) == 2
    texts = dict(fake.sent)
    # The server owner sees both devices; the friend only their own.
    assert "Wochenrückblick" in texts["owner-chat"]
    assert "Brotato" in texts["owner-chat"] or "DayZ" in texts["owner-chat"]
    assert "DayZ" in texts["max-chat"] and "Brotato" not in texts["max-chat"] and "HorstPC" not in texts["max-chat"]
    # Only once per week.
    assert asyncio.run(send_weekly_recaps(database, settings, monday + timedelta(hours=1), fake.transport)) == 0
