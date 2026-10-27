from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base
from pydantic import SecretStr


def test_personal_accounts_authorize_chat_and_revoke_access(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'users.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    app = create_app(
        ServerSettings(
            database_url="sqlite+pysqlite://",
            dashboard_token=SecretStr("legacy-commander-token"),
            dashboard_allow_loopback_without_token=False,
        ),
        database,
    )
    legacy = {"X-NCC-Dashboard-Token": "legacy-commander-token"}
    with TestClient(app) as commander, TestClient(app) as beta:
        created = commander.post(
            "/api/v1/users", headers=legacy,
            json={"username": "alice", "password": "correct horse battery", "role": "beta_tester"},
        )
        assert created.status_code == 201
        user_id = created.json()["user_id"]
        assert commander.get("/api/v1/users", headers=legacy).json()[0]["username"] == "alice"

        assert beta.post("/api/v1/users/login", json={"username": "alice", "password": "wrong"}).status_code == 401
        assert beta.post("/api/v1/users/login", json={"username": "alice", "password": "correct horse battery"}).status_code == 200
        assert beta.get("/api/v1/users/me").json()["username"] == "alice"
        assert beta.get("/api/v1/users").status_code == 403

        # The browser-supplied node ID must never be accepted as chat identity.
        sent = beta.post(
            "/api/v1/fleet/chat/messages",
            json={"sender_node_id": "forged-node", "body": "Hallo Fleet"},
        )
        assert sent.status_code == 201
        assert sent.json()["sender_name"] == "alice"
        assert sent.json()["sender_user_id"] == user_id
        assert sent.json()["sender_node_id"] is None

        backup = commander.post(
            "/api/v1/users", headers=legacy,
            json={"username": "backup", "password": "second-commander-passphrase", "role": "commander"},
        )
        assert backup.status_code == 201
        promoted = commander.patch(f"/api/v1/users/{user_id}", headers=legacy, json={"role": "commander"})
        assert promoted.status_code == 200
        assert beta.get("/api/v1/users").status_code == 200
        demoted = commander.patch(f"/api/v1/users/{user_id}", headers=legacy, json={"role": "beta_tester"})
        assert demoted.status_code == 200
        assert beta.get("/api/v1/users").status_code == 403
        disabled = commander.patch(f"/api/v1/users/{user_id}", headers=legacy, json={"active": False})
        assert disabled.status_code == 200
        assert beta.get("/api/v1/users/me").status_code == 401


def test_password_change_revokes_other_browser_sessions(tmp_path: Path) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'passwords.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    app = create_app(
        ServerSettings(database_url="sqlite+pysqlite://", dashboard_token=SecretStr("legacy-commander-token"), dashboard_allow_loopback_without_token=False),
        database,
    )
    with TestClient(app) as administrator, TestClient(app) as first, TestClient(app) as second:
        created = administrator.post(
            "/api/v1/users", headers={"X-NCC-Dashboard-Token": "legacy-commander-token"},
            json={"username": "brunzel", "password": "initial-passphrase", "role": "commander"},
        )
        assert created.status_code == 201
        credentials = {"username": "brunzel", "password": "initial-passphrase"}
        assert first.post("/api/v1/users/login", json=credentials).status_code == 200
        assert second.post("/api/v1/users/login", json=credentials).status_code == 200
        changed = first.post("/api/v1/users/password", json={"current_password": "initial-passphrase", "new_password": "replacement-passphrase"})
        assert changed.status_code == 204
        assert first.get("/api/v1/users/me").status_code == 200
        assert second.get("/api/v1/users/me").status_code == 401
        assert second.post("/api/v1/users/login", json=credentials).status_code == 401
        assert second.post("/api/v1/users/login", json={"username": "brunzel", "password": "replacement-passphrase"}).status_code == 200
