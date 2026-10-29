from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from ncc_server.agent_tokens import issue_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.game_metadata import refresh_game_metadata
from ncc_server.game_service import playtime_statistics
from ncc_server.models import Base, Game, GameSession, Node, TelemetryPoint, utc_now
from pydantic import SecretStr
from sqlalchemy import select

DASHBOARD = {"X-NCC-Dashboard-Token": "dashboard-secret"}
CYBERPUNK = {"title": "Cyberpunk 2077", "launcher": "steam", "app_id": "1091500", "executable": "Cyberpunk2077.exe"}


def _setup(tmp_path: Path) -> tuple[Database, TestClient, dict[str, str], str]:
    path = tmp_path / "ncc-games.db"
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        plaintext = issue_agent_token(session, "Gaming PC", utc_now() + timedelta(hours=1)).plaintext
    settings = ServerSettings(
        database_url=f"sqlite+pysqlite:///{path.as_posix()}",
        dashboard_token=SecretStr("dashboard-secret"),
        game_metadata_enabled=False,
    )
    client = TestClient(create_app(settings, database))
    agent = {"Authorization": f"Bearer {plaintext}"}
    node_id = client.post("/api/v1/nodes/enroll", headers=agent, json={
        "machine_id": "machine-gaming-1", "display_name": "Gaming PC", "platform": "windows",
        "agent_version": "0.6.0-beta.8", "metadata": {},
    }).json()["node_id"]
    return database, client, agent, node_id


def _point(at: datetime, game: dict[str, object] | None, gpu_temperature: float = 70.0) -> dict[str, object]:
    metrics: dict[str, object] = {
        "cpu": {"percent": 40.0, "temperature_c": 60.0},
        "gpus": [{"percent": 95.0, "temperature_c": gpu_temperature}],
    }
    if game is not None:
        metrics["game"] = game
    return {"sample_id": str(uuid.uuid4()), "recorded_at": at.isoformat(), "metrics": metrics}


def test_game_points_build_sessions_and_switch_gaming_mode_on(tmp_path: Path) -> None:
    database, client, agent, node_id = _setup(tmp_path)
    now = utc_now()
    with client:
        points = [_point(now - timedelta(seconds=30 - 10 * index), CYBERPUNK, 70 + index) for index in range(3)]
        assert client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": points}).json()["accepted"] == 3
        node = client.get(f"/api/v1/fleet/nodes/{node_id}", headers=DASHBOARD).json()
        assert node["now_playing"]["title"] == "Cyberpunk 2077"
        assert node["now_playing"]["launcher"] == "steam"
        assert node["auto_gaming_until"] is not None
        assert node["game_tracking"] == "titles"

        stats = client.get("/api/v1/fleet/games/stats", headers=DASHBOARD, params={"days": 7}).json()
        assert stats["total_seconds"] == 20
        assert stats["session_count"] == 1
        top = stats["games"][0]
        assert top["title"] == "Cyberpunk 2077"
        assert top["hardware"]["gpu_temperature_c"] == {"average": 71.0, "max": 72.0}
        assert stats["nodes"] == [{"node_id": node_id, "display_name": "Gaming PC", "seconds": 20}]
    with database.session() as session:
        game = session.scalar(select(Game))
        assert game is not None and game.key == "steam:1091500" and game.steam_app_id == 1091500


def test_a_pause_longer_than_the_gap_starts_a_new_session(tmp_path: Path) -> None:
    database, client, agent, _ = _setup(tmp_path)
    start = utc_now() - timedelta(hours=2)
    with client:
        points = [
            _point(start, CYBERPUNK), _point(start + timedelta(minutes=1), CYBERPUNK),
            _point(start + timedelta(minutes=20), CYBERPUNK),
            _point(start + timedelta(minutes=21), {"title": "Brotato", "launcher": "steam", "app_id": "1942280"}),
            _point(start + timedelta(minutes=22), None),
        ]
        client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": points})
        node = client.get("/api/v1/fleet/nodes", headers=DASHBOARD).json()[0]
        # Old buffered points neither show as playing nor switch gaming mode on.
        assert node["now_playing"] is None
        assert node["auto_gaming_until"] is None
    with database.session() as session:
        assert session.query(GameSession).count() == 3


def test_privacy_levels_reduce_or_drop_game_data(tmp_path: Path) -> None:
    database, client, agent, node_id = _setup(tmp_path)
    with client:
        assert client.put(f"/api/v1/fleet/nodes/{node_id}/game-settings", json={"game_tracking": "presence", "auto_gaming_mode": False}).status_code in {401, 403}
        response = client.put(
            f"/api/v1/fleet/nodes/{node_id}/game-settings", headers=DASHBOARD,
            json={"game_tracking": "presence", "auto_gaming_mode": False},
        )
        assert response.status_code == 200
        client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": [_point(utc_now(), CYBERPUNK)]})
        node = client.get(f"/api/v1/fleet/nodes/{node_id}", headers=DASHBOARD).json()
        assert node["now_playing"]["title"] is None
        assert node["auto_gaming_until"] is None

        client.put(f"/api/v1/fleet/nodes/{node_id}/game-settings", headers=DASHBOARD, json={"game_tracking": "off", "auto_gaming_mode": True})
        client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": [_point(utc_now() + timedelta(seconds=5), CYBERPUNK)]})
    with database.session() as session:
        payloads = [point.payload for point in session.scalars(select(TelemetryPoint).order_by(TelemetryPoint.recorded_at))]
        assert payloads[0]["game"] == {"active": True}
        assert "game" not in payloads[1]
        assert session.scalar(select(Game)) is None
        assert session.query(GameSession).count() == 1


def test_statistics_split_sessions_over_local_days_and_hours(tmp_path: Path) -> None:
    database, client, agent, node_id = _setup(tmp_path)
    with database.session() as session:
        game = Game(key="name:test", title="Test", launcher="gog", genres=[], developers=[])
        session.add(game)
        session.flush()
        # 23:30 to 00:30 UTC; with a +60 minute offset that is 00:30 to 01:30 local.
        start = datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc)
        session.add(GameSession(node_id=node_id, game_id=game.id, started_at=start, ended_at=start + timedelta(hours=1), sample_count=2, hardware={}))
        session.commit()
        utc = playtime_statistics(session, days=0, node_id=None, utc_offset_minutes=0)
        local = playtime_statistics(session, days=0, node_id=None, utc_offset_minutes=60)
    assert utc["daily"] == [{"date": "2026-10-25", "seconds": 1800}, {"date": "2026-10-26", "seconds": 1800}]
    assert local["daily"] == [{"date": "2026-10-26", "seconds": 3600}]
    # 2026-10-26 is a Monday (weekday 0).
    assert local["heatmap"][0][0] == 1800 and local["heatmap"][0][1] == 1800
    assert local["longest_session"]["seconds"] == 3600


def test_metadata_is_fetched_from_steam_and_served_by_ncc(tmp_path: Path) -> None:
    database, client, agent, _ = _setup(tmp_path)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url.host) + request.url.path)
        if request.url.path == "/api/storesearch/":
            return httpx.Response(200, json={"items": [{"id": 1, "name": "Two Point Hospitals"}, {"id": 535930, "name": "Two Point Hospital™"}]})
        if request.url.path == "/api/appdetails":
            app_id = request.url.params["appids"]
            return httpx.Response(200, json={app_id: {"success": True, "data": {
                "name": "Two Point Hospital", "short_description": "Baue Krankenhäuser.",
                "genres": [{"description": "Simulation"}], "developers": ["Two Point Studios"],
                "release_date": {"date": "30. Aug. 2018"},
                "header_image": "https://shared.akamai.steamstatic.com/header.jpg?t=1",
            }}})
        if request.url.host.endswith("steamstatic.com"):
            return httpx.Response(200, content=b"jpeg-bytes", headers={"content-type": "image/jpeg"})
        return httpx.Response(404)

    with client:
        client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": [
            _point(utc_now(), {"title": "Two Point Hospital", "launcher": "epic", "app_id": "4ad17ed6"}),
        ]})
        assert asyncio.run(refresh_game_metadata(database, httpx.MockTransport(handler))) == 1
        game = client.get("/api/v1/fleet/games", headers=DASHBOARD).json()[0]
        assert game["steam_app_id"] == 535930
        assert game["match_state"] == "matched"
        assert game["genres"] == ["Simulation"]
        assert game["has_artwork"] is True
        artwork = client.get(f"/api/v1/fleet/games/{game['game_id']}/artwork", headers=DASHBOARD)
        assert artwork.content == b"jpeg-bytes" and artwork.headers["content-type"] == "image/jpeg"
        assert client.get(f"/api/v1/fleet/games/{game['game_id']}/artwork").status_code in {401, 403}
        # Nothing is fetched again once a game is matched.
        assert asyncio.run(refresh_game_metadata(database, httpx.MockTransport(handler))) == 0

        corrected = client.patch(f"/api/v1/fleet/games/{game['game_id']}", headers=DASHBOARD, json={"steam_app_id": None})
        assert corrected.json()["match_state"] == "none" and corrected.json()["has_artwork"] is False
    assert requests[0] == "store.steampowered.com/api/storesearch/"


def test_unknown_games_are_marked_without_a_store_match(tmp_path: Path) -> None:
    database, client, agent, _ = _setup(tmp_path)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"items": []}))
    with client:
        client.post("/api/v1/nodes/telemetry", headers=agent, json={"points": [
            _point(utc_now(), {"title": "Homebrew", "launcher": "xbox"}),
        ]})
        asyncio.run(refresh_game_metadata(database, transport))
    with database.session() as session:
        game = session.scalar(select(Game))
        assert game is not None and game.match_state == "none" and game.key == "name:homebrew"
        node = session.scalar(select(Node))
        assert node is not None and node.auto_gaming_until is not None
