from __future__ import annotations

from fastapi.testclient import TestClient
from ncc import __version__
from ncc.app import _allowed_origin, app
from ncc.config import get_settings

BASE_URL = "http://127.0.0.1:8350"


def test_core_api_and_security_headers() -> None:
    assert app.version == __version__
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.get("/api/metrics")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "metrics" in response.json()
        assert client.get("/api/multipc/mode").json()["mode"] in {"local", "server", "client"}
        assert client.get("/api/sensors/capabilities").status_code == 200


def test_rejects_foreign_origin() -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.get("/api/metrics", headers={"Origin": "https://evil.example"})
        assert response.status_code == 403


def test_accepts_same_origin_lan_host() -> None:
    assert _allowed_origin("http://192.168.1.20:8350", "192.168.1.20:8350")


def test_writes_require_valid_token_for_non_loopback_client() -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        payload = {"alias": "tester", "pc_name": "test-pc"}
        assert client.post("/api/profile", json=payload).status_code == 401
        assert client.post(
            "/api/profile", json=payload, headers={"X-NCC-Token": "wrong"}
        ).status_code == 401
        assert client.post(
            "/api/profile", json=payload, headers={"X-NCC-Token": get_settings().token}
        ).status_code == 200


def test_live_websocket() -> None:
    with TestClient(app, base_url=BASE_URL) as client, client.websocket_connect(
        f"/ws/live?token={get_settings().token}", headers={"host": "127.0.0.1:8350"}
    ) as websocket:
        snapshot = websocket.receive_json()
        assert "node_id" in snapshot

