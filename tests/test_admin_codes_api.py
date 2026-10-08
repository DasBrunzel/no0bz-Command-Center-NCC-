from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base
from pydantic import SecretStr


def make_database(path: Path) -> Database:
    database = Database(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(database.engine)
    return database


def test_admin_code_creates_a_browser_session_and_can_be_revoked(tmp_path: Path) -> None:
    database = make_database(tmp_path / "admin-codes.db")
    app = create_app(
        ServerSettings(
            database_url="sqlite+pysqlite://",
            dashboard_token=SecretStr("dashboard-secret"),
            dashboard_allow_loopback_without_token=False,
        ),
        database,
    )
    legacy_headers = {"X-NCC-Dashboard-Token": "dashboard-secret"}

    with TestClient(app) as administrator:
        created = administrator.post(
            "/api/v1/admin-codes",
            headers=legacy_headers,
            json={"label": "  Pixel   7  ", "expires_minutes": 15},
        )
        assert created.status_code == 201
        payload = created.json()
        assert len(payload["code"]) == 8
        assert payload["code"].isalnum()

        with TestClient(app) as browser:
            redeemed = browser.post("/api/v1/admin-codes/redeem", json={"code": payload["code"]})
            assert redeemed.status_code == 200
            assert "ncc_dashboard_session" in redeemed.headers["set-cookie"]
            assert browser.get("/api/v1/admin-codes").status_code == 200

            codes = administrator.get("/api/v1/admin-codes", headers=legacy_headers)
            assert codes.status_code == 200
            assert codes.json()[0]["label"] == "Pixel 7"
            assert codes.json()[0]["status"] == "used"

            revoked = administrator.post(
                f"/api/v1/admin-codes/{codes.json()[0]['code_id']}/revoke",
                headers=legacy_headers,
            )
            assert revoked.status_code == 200
            assert revoked.json()["status"] == "revoked"
            assert browser.get("/api/v1/admin-codes").status_code == 401


def test_admin_code_cannot_be_redeemed_twice(tmp_path: Path) -> None:
    database = make_database(tmp_path / "one-time-code.db")
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token=SecretStr("dashboard-secret")),
        database,
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/admin-codes",
            headers={"X-NCC-Dashboard-Token": "dashboard-secret"},
            json={"label": "Laptop"},
        )
        code = created.json()["code"]
        assert client.post("/api/v1/admin-codes/redeem", json={"code": code}).status_code == 200
        assert client.post("/api/v1/admin-codes/redeem", json={"code": code}).status_code == 401


def test_beta_tester_code_is_badged_and_cannot_manage_or_delete(tmp_path: Path) -> None:
    database = make_database(tmp_path / "beta-tester.db")
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token=SecretStr("dashboard-secret")),
        database,
    )
    commander_headers = {"X-NCC-Dashboard-Token": "dashboard-secret"}
    with TestClient(app) as commander:
        invitation = commander.post(
            "/api/v1/agent-invitations",
            headers=commander_headers,
            json={"name": "Test-PC", "expires_hours": 24},
        ).json()
        created = commander.post(
            "/api/v1/admin-codes",
            headers=commander_headers,
            json={"label": "Beta Friend", "beta_tester": True},
        )
        assert created.status_code == 201
        assert created.json()["access_role"] == "beta_tester"

        with TestClient(app) as beta_tester:
            assert beta_tester.post(
                "/api/v1/admin-codes/redeem", json={"code": created.json()["code"]}
            ).status_code == 200
            assert beta_tester.get("/api/v1/admin-codes/access").json() == {
                "access_role": "beta_tester"
            }
            assert beta_tester.post(
                "/api/v1/admin-codes", json={"label": "Escalation"}
            ).status_code == 403
            assert beta_tester.delete(
                f"/api/v1/agent-invitations/{invitation['token_id']}"
            ).status_code == 403
