from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class FakeDatabase:
    def __init__(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self._sessions = sessionmaker(bind=self.engine)

    def ping(self) -> None:
        with self.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1

    def sessions(self) -> Iterator[Session]:
        with self._sessions() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


def test_server_has_versioned_api_and_fleet_browser_gui() -> None:
    database = FakeDatabase()
    settings = ServerSettings(database_url="sqlite+pysqlite:///:memory:")
    application = create_app(settings, database)  # type: ignore[arg-type]
    with TestClient(application) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert 'id="root"' in root.text
        assert root.headers["x-content-type-options"] == "nosniff"
        assert client.get("/api/v1/status/live").status_code == 200
        assert client.get("/api/v1/status/ready").status_code == 200
        assert client.get("/api/v1/version").json()["api"] == "v1"
        assert client.get("/assets/index.js").status_code == 404


def test_foundation_metadata_contains_persistent_entities() -> None:
    assert set(Base.metadata.tables) == {
        "alert_states",
        "admin_codes",
        "agent_pairings",
        "agent_tokens",
        "audit_events",
        "dashboard_sessions",
        "nodes",
        "telemetry_points",
        "users",
    }


def test_readiness_reports_unavailable_database() -> None:
    database = FakeDatabase()

    def unavailable() -> None:
        raise OSError("database offline")

    database.ping = unavailable
    settings = ServerSettings(
        database_url="sqlite+pysqlite:///:memory:",
        database_check_on_start=False,
    )
    application = create_app(settings, database)  # type: ignore[arg-type]
    with TestClient(application) as client:
        response = client.get("/api/v1/status/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "database unavailable"}
