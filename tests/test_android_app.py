from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base, Node
from pydantic import SecretStr

DASHBOARD = {"X-NCC-Dashboard-Token": "dashboard-secret"}
APK = b"PK\x03\x04" + b"fake-apk-content" * 1000


def make_app(tmp_path: Path):  # type: ignore[no-untyped-def]
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'app.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    settings = ServerSettings(
        database_url="sqlite+pysqlite://",
        dashboard_token=SecretStr("dashboard-secret"),
        android_release_dir=tmp_path / "release",
    )
    return create_app(settings, database), database


def pair(client: TestClient) -> tuple[dict[str, str], str]:
    identity = {
        "machine_id": "android-app-0000000001",
        "display_name": "Testhandy",
        "platform": "android",
        "agent_version": "0.6.0",
        "metadata": {"heartbeat_interval_seconds": 60},
    }
    pairing = {**identity, "pairing_id": "android_app_pairing_01", "pairing_secret": "s" * 43}
    assert client.post("/api/v1/agent-pairings/register", json=pairing).status_code == 201
    assert client.post("/api/v1/agent-pairings/android_app_pairing_01/approve", headers=DASHBOARD).status_code == 200
    token = client.post("/api/v1/agent-pairings/android_app_pairing_01/claim", json={"pairing_secret": "s" * 43}).json()["token"]
    agent = {"Authorization": f"Bearer {token}"}
    node_id = client.post("/api/v1/nodes/enroll", json=identity, headers=agent).json()["node_id"]
    return agent, node_id


def upload(client: TestClient, code: int, name: str, content: bytes = APK):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/android/release",
        files={"file": ("ncc-android.apk", content, "application/vnd.android.package-archive")},
        data={"version_code": str(code), "version_name": name, "notes": "Neu: Widget"},
        headers=DASHBOARD,
    )


def test_commander_uploads_an_apk_and_the_phone_downloads_it(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        agent, _ = pair(client)
        assert client.get("/api/v1/nodes/app-release", headers=agent).json() is None
        assert client.get("/api/v1/nodes/app-release/apk", headers=agent).status_code == 404

        with client.websocket_connect("/api/v1/nodes/stream", headers=agent) as ws:
            assert ws.receive_json()["type"] == "alert.snapshot"
            stored = upload(client, 6, "0.6.0")
            assert stored.status_code == 201
            assert stored.json()["sha256"] == hashlib.sha256(APK).hexdigest()
            event = ws.receive_json()
            assert event["type"] == "app.update" and event["release"]["version_code"] == 6

        info = client.get("/api/v1/nodes/app-release", headers=agent).json()
        assert (info["version_code"], info["version_name"], info["size"], info["notes"]) == (6, "0.6.0", len(APK), "Neu: Widget")
        apk = client.get("/api/v1/nodes/app-release/apk", headers=agent)
        assert apk.status_code == 200 and apk.content == APK
        assert apk.headers["content-type"] == "application/vnd.android.package-archive"
        assert client.get("/api/v1/android/release", headers=DASHBOARD).json()["version_name"] == "0.6.0"


def test_upload_rejects_older_versions_and_non_apk_files(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        assert upload(client, 6, "0.6.0").status_code == 201
        assert upload(client, 6, "0.6.0-again").status_code == 409
        assert upload(client, 5, "0.5.0").status_code == 409
        assert upload(client, 7, "0.7.0", content=b"<html>kein apk</html>").status_code == 422
        assert upload(client, 7, "bad name!").status_code == 422
        # A failed upload keeps the previous release intact.
        assert client.get("/api/v1/android/release", headers=DASHBOARD).json()["version_code"] == 6
        assert not list((tmp_path / "release").glob("*.part"))


def test_release_routes_need_the_right_access(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/v1/android/release", files={"file": ("a.apk", APK)}, data={"version_code": "1", "version_name": "1"}).status_code == 401
        assert client.get("/api/v1/nodes/app-release").status_code == 401
        assert client.get("/api/v1/nodes/app-release/apk", headers=DASHBOARD).status_code == 401


def test_dashboard_changes_settings_of_a_connected_phone(tmp_path: Path) -> None:
    app, database = make_app(tmp_path)
    with TestClient(app) as client:
        agent, node_id = pair(client)
        url = f"/api/v1/fleet/nodes/{node_id}/app-config"
        # Not connected: the change cannot reach the phone.
        assert client.put(url, json={"interval_seconds": 120}, headers=DASHBOARD).status_code == 409
        with client.websocket_connect("/api/v1/nodes/stream", headers=agent) as ws:
            ws.receive_json()
            assert client.put(url, json={"interval_seconds": 120, "upload_rule": "immediate"}, headers=DASHBOARD).status_code == 204
            assert ws.receive_json() == {"type": "config.update", "interval_seconds": 120, "upload_rule": "immediate"}
            assert client.put(url, json={"interval_seconds": 45}, headers=DASHBOARD).status_code == 422
            assert client.put(url, json={}, headers=DASHBOARD).status_code == 422

        with database.session() as session:
            pc = Node(machine_id="pc-000000000001", display_name="PC", platform="windows", approved=True)
            session.add(pc)
            session.commit()
            pc_id = pc.id
        assert client.put(f"/api/v1/fleet/nodes/{pc_id}/app-config", json={"interval_seconds": 60}, headers=DASHBOARD).status_code == 422
