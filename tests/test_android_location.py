from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

import httpx
import pytest
from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base, LocationPoint, TelemetryPoint, utc_now
from pydantic import SecretStr
from sqlalchemy import select

DASHBOARD = {"X-NCC-Dashboard-Token": "dashboard-secret"}


def make_app(tmp_path: Path):  # type: ignore[no-untyped-def]
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'location.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(
        database_url="sqlite+pysqlite://",
        dashboard_token=SecretStr("dashboard-secret"),
        map_tile_url="https://tiles.invalid/{z}/{x}/{y}.png",
        map_tile_cache_dir=tmp_path / "tiles",
    )
    return create_app(settings, database), database


def pair(client: TestClient) -> tuple[dict[str, str], str]:
    identity = {
        "machine_id": "android-location-000001",
        "display_name": "Testhandy",
        "platform": "android",
        "agent_version": "0.5.0",
        "metadata": {"heartbeat_interval_seconds": 60},
    }
    pairing = {**identity, "pairing_id": "android_location_pairing", "pairing_secret": "s" * 43}
    assert client.post("/api/v1/agent-pairings/register", json=pairing).status_code == 201
    assert client.post("/api/v1/agent-pairings/android_location_pairing/approve", headers=DASHBOARD).status_code == 200
    token = client.post("/api/v1/agent-pairings/android_location_pairing/claim", json={"pairing_secret": "s" * 43}).json()["token"]
    agent = {"Authorization": f"Bearer {token}"}
    node_id = client.post("/api/v1/nodes/enroll", json=identity, headers=agent).json()["node_id"]
    return agent, node_id


def point(lat: float, lon: float, minutes_ago: int = 0, accuracy: float = 8.0) -> dict[str, object]:
    return {
        "sample_id": str(uuid4()),
        "recorded_at": (utc_now() - timedelta(minutes=minutes_ago)).isoformat(),
        "metrics": {"battery": {"percent": 50}, "location": {"lat": lat, "lon": lon, "accuracy_m": accuracy}},
    }


def test_locations_are_ignored_and_stripped_until_tracking_is_switched_on(tmp_path: Path) -> None:
    app, database = make_app(tmp_path)
    with TestClient(app) as client:
        agent, node_id = pair(client)
        heartbeat = client.post("/api/v1/nodes/heartbeat", json={"agent_version": "0.5.0", "metadata": {}}, headers=agent)
        assert heartbeat.json()["location_tracking"] is False

        assert client.post("/api/v1/nodes/telemetry", json={"points": [point(52.52, 13.405)]}, headers=agent).status_code == 200
        with database.session() as session:
            assert session.scalars(select(LocationPoint)).all() == []
            # The fix is never kept inside the telemetry payload, even when tracking is off.
            payload = session.scalars(select(TelemetryPoint)).one().payload
            assert "location" not in payload and payload["battery"] == {"percent": 50}


def test_app_switch_records_heatmap_cells_and_gpx(tmp_path: Path) -> None:
    app, database = make_app(tmp_path)
    with TestClient(app) as client:
        agent, node_id = pair(client)
        assert client.put("/api/v1/nodes/location-tracking", json={"enabled": True}, headers=agent).json() == {"enabled": True}
        assert client.post("/api/v1/nodes/heartbeat", json={"agent_version": "0.5.0", "metadata": {}}, headers=agent).json()["location_tracking"]

        points = [
            point(52.520001, 13.405001, 30),
            point(52.520002, 13.405002, 20),  # same ~11 m cell
            point(48.137, 11.575, 10),
            point(1.0, 1.0, 5, accuracy=900),  # too inaccurate
            point(95.0, 1.0, 4),  # impossible latitude
        ]
        assert client.post("/api/v1/nodes/telemetry", json={"points": points}, headers=agent).json()["accepted"] == 5

        heat = client.get(f"/api/v1/fleet/nodes/{node_id}/locations?days=7", headers=DASHBOARD).json()
        assert heat["points"] == 3 and heat["stored_points"] == 3
        assert heat["cells"][0] == [52.52, 13.405, 2]
        assert heat["cells"][1] == [48.137, 11.575, 1]

        node = next(n for n in client.get("/api/v1/fleet/nodes", headers=DASHBOARD).json() if n["node_id"] == node_id)
        assert node["location_tracking"] is True

        gpx = client.get(f"/api/v1/fleet/nodes/{node_id}/locations.gpx?days=7", headers=DASHBOARD)
        assert gpx.status_code == 200 and gpx.headers["content-type"].startswith("application/gpx+xml")
        root = ElementTree.fromstring(gpx.text)
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        assert len(root.findall(".//g:trkpt", ns)) == 3
        assert root.find(".//g:trk/g:name", ns).text == "Testhandy"  # type: ignore[union-attr]


def test_dashboard_switch_reaches_the_phone_live_and_deletion_removes_history(tmp_path: Path) -> None:
    app, database = make_app(tmp_path)
    with TestClient(app) as client:
        agent, node_id = pair(client)
        with client.websocket_connect("/api/v1/nodes/stream", headers=agent) as ws:
            assert ws.receive_json()["type"] == "alert.snapshot"
            assert client.put(f"/api/v1/fleet/nodes/{node_id}/location-tracking", json={"enabled": True}, headers=DASHBOARD).status_code == 200
            assert ws.receive_json() == {"type": "config.update", "location_tracking": True}

        client.post("/api/v1/nodes/telemetry", json={"points": [point(52.52, 13.405, 2), point(52.53, 13.41, 1)]}, headers=agent)
        assert client.delete(f"/api/v1/fleet/nodes/{node_id}/locations", headers=DASHBOARD).json() == {"deleted": 2}
        client.post("/api/v1/nodes/telemetry", json={"points": [point(52.52, 13.405)]}, headers=agent)
        assert client.delete("/api/v1/nodes/locations", headers=agent).json() == {"deleted": 1}
        with database.session() as session:
            assert session.scalars(select(LocationPoint)).all() == []


def test_location_routes_need_the_right_access(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        _, node_id = pair(client)
        assert client.get(f"/api/v1/fleet/nodes/{node_id}/locations").status_code == 401
        assert client.put(f"/api/v1/fleet/nodes/{node_id}/location-tracking", json={"enabled": True}).status_code == 401
        assert client.put("/api/v1/nodes/location-tracking", json={"enabled": True}, headers=DASHBOARD).status_code == 401
        assert client.get("/api/v1/fleet/nodes/unknown/locations", headers=DASHBOARD).status_code == 404
        assert client.get("/api/v1/map/tiles/3/1/1.png").status_code == 401


def test_map_tiles_are_proxied_and_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = make_app(tmp_path)
    calls: list[str] = []

    async def fake_get(self: httpx.AsyncClient, url: str, **_: object) -> httpx.Response:
        calls.append(url)
        assert self.headers["User-Agent"].startswith("no0bz-Command-Center/")
        return httpx.Response(200, content=b"PNGDATA", headers={"content-type": "image/png"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with TestClient(app) as client:
        first = client.get("/api/v1/map/tiles/12/2200/1343.png", headers=DASHBOARD)
        assert first.status_code == 200 and first.content == b"PNGDATA"
        assert client.get("/api/v1/map/tiles/12/2200/1343.png", headers=DASHBOARD).content == b"PNGDATA"
        assert calls == ["https://tiles.invalid/12/2200/1343.png"]  # second request from cache
        assert (tmp_path / "tiles" / "12" / "2200" / "1343.png").read_bytes() == b"PNGDATA"
        assert client.get("/api/v1/map/tiles/2/9/0.png", headers=DASHBOARD).status_code == 404
        assert client.get("/api/v1/map/tiles/20/0/0.png", headers=DASHBOARD).status_code == 404
