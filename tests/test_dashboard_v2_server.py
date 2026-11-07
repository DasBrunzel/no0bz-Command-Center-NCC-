"""Server changes for the 0.7 dashboard: compression, root service worker,
rejecting pairings, the SteamGridDB banner search and Gaming Mode for beta testers."""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from ncc_server import app as app_module
from ncc_server.agent_tokens import issue_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import AgentPairing, AuditEvent, Base, Game, utc_now
from pydantic import SecretStr
from sqlalchemy import select

COMMANDER = {"X-NCC-Dashboard-Token": "dashboard-secret"}
PNG = b"\x89PNG\r\n\x1a\n" + b"banner-bytes"
WEBP = b"RIFF\x00\x00\x00\x00WEBPthumb"


def _app(tmp_path: Path, steamgriddb_key: str = ""):  # type: ignore[no-untyped-def]
    path = tmp_path / "ncc-v2.db"
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(
        database_url=f"sqlite+pysqlite:///{path.as_posix()}", dashboard_token=SecretStr("dashboard-secret"),
        dashboard_allow_loopback_without_token=False, game_metadata_enabled=False,
        steamgriddb_api_key=SecretStr(steamgriddb_key),
    )
    return database, create_app(settings, database)


def _beta(app, commander: TestClient) -> TestClient:  # type: ignore[no-untyped-def]
    code = commander.post("/api/v1/admin-codes", headers=COMMANDER, json={"label": "Beta", "beta_tester": True}).json()["code"]
    beta = TestClient(app)
    assert beta.post("/api/v1/admin-codes/redeem", json={"code": code}).status_code == 200
    return beta


def _node(database: Database, client: TestClient) -> str:
    with database.session() as session:
        token = issue_agent_token(session, "Kalle-PC", utc_now() + timedelta(hours=1)).plaintext
    return str(client.post("/api/v1/nodes/enroll", headers={"Authorization": f"Bearer {token}"}, json={
        "machine_id": f"machine-{uuid.uuid4().hex[:12]}", "display_name": "Kalle-PC", "platform": "windows",
        "agent_version": "0.6.2", "metadata": {},
    }).json()["node_id"])


def _register(client: TestClient, pairing_id: str, secret: str):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/agent-pairings/register", json={
        "pairing_id": pairing_id, "pairing_secret": secret, "machine_id": "machine-stranger-1",
        "display_name": "Fremder PC", "platform": "windows", "agent_version": "0.6.2", "metadata": {},
    })


# ── Compression and service worker ────────────────────────────────────────

@pytest.fixture
def static_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html>" + "<p>no0bz</p>" * 400, encoding="utf-8")
    (root / "assets" / "index.js").write_text("console.log('ncc');" * 400, encoding="utf-8")
    (root / "sw.js").write_text("self.addEventListener('fetch', () => {});" * 40, encoding="utf-8")
    monkeypatch.setattr(app_module, "STATIC_DIR", root)
    return root


def test_dashboard_files_are_compressed_but_api_responses_are_not(tmp_path: Path, static_dir: Path) -> None:
    _, app = _app(tmp_path)
    with TestClient(app) as client:
        gzip = {"Accept-Encoding": "gzip"}
        page = client.get("/", headers=gzip)
        assert page.status_code == 200 and page.headers.get("content-encoding") == "gzip"
        assert page.headers["cache-control"] == "no-cache"
        script = client.get("/assets/index.js", headers=gzip)
        assert script.headers.get("content-encoding") == "gzip" and "console.log" in script.text
        nodes = client.get("/api/v1/fleet/nodes", headers={**gzip, **COMMANDER})
        assert nodes.status_code == 200 and "content-encoding" not in nodes.headers
        # Security headers still apply to compressed responses.
        assert "Content-Security-Policy" in page.headers


def test_service_worker_is_served_at_the_root_without_caching(tmp_path: Path, static_dir: Path) -> None:
    _, app = _app(tmp_path)
    with TestClient(app) as client:
        worker = client.get("/sw.js")
        assert worker.status_code == 200
        assert worker.headers["content-type"].startswith("text/javascript")
        assert worker.headers["cache-control"] == "no-cache"
    (static_dir / "sw.js").unlink()
    with TestClient(app) as client:
        assert client.get("/sw.js").status_code == 404


# ── Rejecting pairing requests ────────────────────────────────────────────

def test_commanders_reject_a_pairing_request_which_can_then_not_be_approved(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    pairing_id, secret = f"pairing_{uuid.uuid4().hex[:16]}", uuid.uuid4().hex * 2
    with TestClient(app) as commander:
        assert _register(commander, pairing_id, secret).status_code == 201
        beta = _beta(app, commander)
        assert beta.post(f"/api/v1/agent-pairings/{pairing_id}/cancel").status_code == 403
        rejected = commander.post(f"/api/v1/agent-pairings/{pairing_id}/cancel", headers=COMMANDER)
        assert rejected.status_code == 200 and rejected.json()["status"] == "cancelled"
        assert commander.post(f"/api/v1/agent-pairings/{pairing_id}/approve", headers=COMMANDER).status_code == 404
        assert commander.post(f"/api/v1/agent-pairings/{pairing_id}/claim", json={"pairing_secret": secret}).status_code == 410
        # Within one request lifetime the agent cannot reopen it.
        assert _register(commander, pairing_id, secret).status_code == 409
        assert commander.post("/api/v1/agent-pairings/missing-pairing-id-1/cancel", headers=COMMANDER).status_code == 404
    with database.session() as session:
        assert session.scalar(select(AuditEvent).where(AuditEvent.action == "agent-pairing.cancelled")) is not None
        record = session.get(AgentPairing, pairing_id)
        assert record is not None
        record.cancelled_at = utc_now() - timedelta(minutes=16)
        session.commit()
    with TestClient(app) as commander:
        # Afterwards the device may ask again, but needs a fresh approval.
        reopened = _register(commander, pairing_id, secret)
        assert reopened.status_code == 201 and reopened.json()["status"] == "waiting"
        assert commander.post(f"/api/v1/agent-pairings/{pairing_id}/claim", json={"pairing_secret": secret}).status_code == 409


def test_a_claimed_pairing_cannot_be_rejected(tmp_path: Path) -> None:
    _, app = _app(tmp_path)
    pairing_id, secret = f"pairing_{uuid.uuid4().hex[:16]}", uuid.uuid4().hex * 2
    with TestClient(app) as commander:
        _register(commander, pairing_id, secret)
        commander.post(f"/api/v1/agent-pairings/{pairing_id}/approve", headers=COMMANDER)
        assert commander.post(f"/api/v1/agent-pairings/{pairing_id}/claim", json={"pairing_secret": secret}).status_code == 200
        assert commander.post(f"/api/v1/agent-pairings/{pairing_id}/cancel", headers=COMMANDER).status_code == 409


# ── SteamGridDB banner search ─────────────────────────────────────────────

def _grid_transport(calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.startswith("/api/v2/search/autocomplete/"):
            return httpx.Response(200, json={"success": True, "data": [{"id": 7, "name": "World of Warcraft"}]})
        if request.url.path == "/api/v2/grids/game/7":
            return httpx.Response(200, json={"success": True, "data": [
                {"id": 1, "score": 1, "url": "https://evil.example/banner.png", "width": 920, "height": 430},
                {"id": 2, "score": 9, "url": "https://cdn2.steamgriddb.com/grid/full.png", "thumb": "https://cdn2.steamgriddb.com/thumb/small.webp", "width": 920, "height": 430, "style": "alternate"},
            ]})
        if request.url.path == "/grid/full.png":
            return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        if request.url.path == "/thumb/small.webp":
            return httpx.Response(200, content=WEBP, headers={"content-type": "image/webp"})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def _game(database: Database) -> str:
    with database.session() as session:
        game = Game(key="battlenet:wow", title="World of Warcraft", launcher="battlenet", match_state="none")
        session.add(game)
        session.commit()
        return game.id


def test_banner_search_needs_a_key_and_commander_rights(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    game_id = _game(database)
    with TestClient(app) as commander:
        missing = commander.get(f"/api/v1/fleet/games/{game_id}/artwork/candidates", headers=COMMANDER)
        assert missing.status_code == 503
        beta = _beta(app, commander)
        assert beta.get(f"/api/v1/fleet/games/{game_id}/artwork/candidates").status_code == 403


def test_commanders_pick_a_steamgriddb_banner_that_is_kept_like_an_upload(tmp_path: Path) -> None:
    database, app = _app(tmp_path, steamgriddb_key="grid-key")
    calls: list[httpx.Request] = []
    app.state.steamgriddb_transport = _grid_transport(calls)
    game_id = _game(database)
    with TestClient(app) as commander:
        found = commander.get(f"/api/v1/fleet/games/{game_id}/artwork/candidates", headers=COMMANDER, params={"query": "WoW"})
        assert found.status_code == 200, found.text
        candidates = found.json()
        assert [item["game_name"] for item in candidates] == ["World of Warcraft", "World of Warcraft"]
        best = candidates[0]
        assert best["style"] == "alternate" and best["preview_url"].endswith("/candidates/0/preview")
        assert all(request.headers["authorization"] == "Bearer grid-key" for request in calls if request.url.host == "www.steamgriddb.com")

        preview = commander.get(best["preview_url"], headers=COMMANDER)
        assert preview.status_code == 200 and preview.content == WEBP and preview.headers["content-type"] == "image/webp"
        # A candidate pointing elsewhere is never downloaded.
        assert commander.get(f"/api/v1/fleet/games/{game_id}/artwork/candidates/1/preview", headers=COMMANDER).status_code == 404
        assert not any(request.url.host == "evil.example" for request in calls)

        chosen = commander.post(f"/api/v1/fleet/games/{game_id}/artwork/candidates/0", headers=COMMANDER)
        assert chosen.status_code == 200 and chosen.json()["artwork_source"] == "upload" and chosen.json()["has_artwork"] is True
        assert commander.get(f"/api/v1/fleet/games/{game_id}/artwork", headers=COMMANDER).content == PNG
        assert commander.post(f"/api/v1/fleet/games/{game_id}/artwork/candidates/9", headers=COMMANDER).status_code == 404
    with database.session() as session:
        event = session.scalar(select(AuditEvent).where(AuditEvent.action == "game.artwork.uploaded"))
        assert event is not None and '"origin":"steamgriddb"' in (event.details or "")


# ── Gaming Mode for beta testers ──────────────────────────────────────────

def test_beta_testers_switch_gaming_mode_but_nothing_else(tmp_path: Path) -> None:
    database, app = _app(tmp_path)
    with TestClient(app) as commander:
        node_id = _node(database, commander)
        beta = _beta(app, commander)
        switched = beta.put(f"/api/v1/fleet/nodes/{node_id}/gaming-mode", json={"minutes": 60})
        assert switched.status_code == 200 and switched.json()["gaming_mode_until"] is not None
        assert beta.put(f"/api/v1/fleet/nodes/{node_id}/gaming-mode", json={"minutes": 0}).json()["gaming_mode_until"] is None
        # Renaming, labels and game settings stay commander/owner only.
        assert beta.patch(f"/api/v1/fleet/nodes/{node_id}", json={"display_name": "Neu"}).status_code == 403
        assert beta.put(f"/api/v1/fleet/nodes/{node_id}/game-settings", json={"game_tracking": "off", "auto_gaming_mode": False}).status_code == 403
        assert beta.put("/api/v1/fleet/nodes/missing/gaming-mode", json={"minutes": 10}).status_code == 404
