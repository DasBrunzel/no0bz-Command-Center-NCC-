from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from ncc_agent.buffer import TelemetryBuffer
from ncc_agent.client import AgentClient
from ncc_agent.config import AgentSettings
from ncc_agent.identity import load_or_create_machine_id
from ncc_agent.runner import _is_new_snapshot
from ncc_server.agent_tokens import issue_agent_token
from ncc_server.app import create_app
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base, TelemetryPoint, utc_now
from pydantic import SecretStr


def test_machine_identity_is_stable_and_private(tmp_path: Path) -> None:
    first = load_or_create_machine_id(tmp_path)
    second = load_or_create_machine_id(tmp_path)
    assert first == second
    assert first.startswith("ncc-")
    assert (tmp_path / "machine-id").read_text(encoding="utf-8").strip() == first.removeprefix(
        "ncc-"
    )


def test_agent_queues_each_collector_snapshot_only_once() -> None:
    assert _is_new_snapshot(10.0, None)
    assert _is_new_snapshot(10.1, 10.0)
    assert not _is_new_snapshot(10.0, 10.0)
    assert not _is_new_snapshot(9.9, 10.0)


def test_invalid_machine_identity_is_not_silently_replaced(tmp_path: Path) -> None:
    tmp_path.joinpath("machine-id").write_text("not-a-uuid", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid NCC agent identity"):
        load_or_create_machine_id(tmp_path)


def test_offline_buffer_is_bounded_fifo_and_persistent(tmp_path: Path) -> None:
    path = tmp_path / "buffer.sqlite3"
    buffer = TelemetryBuffer(path, max_points=2)
    first = buffer.append({"value": 1})
    second = buffer.append({"value": 2})
    third = buffer.append({"value": 3})
    assert first not in {point.sample_id for point in buffer.peek(10)}
    assert [point.sample_id for point in buffer.peek(10)] == [second, third]
    row_to_ack = buffer.peek(1)[0]
    buffer.acknowledge([row_to_ack.row_id])
    buffer.close()

    reopened = TelemetryBuffer(path, max_points=2)
    assert [point.sample_id for point in reopened.peek(10)] == [third]
    reopened.close()


def test_agent_enrolls_and_flushes_buffer_without_exposing_token(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/enroll"):
            return httpx.Response(200, json={"heartbeat_interval_seconds": 14})
        if request.url.path.endswith("/heartbeat"):
            return httpx.Response(200, json={"accepted": True})
        if request.url.path.endswith("/telemetry"):
            return httpx.Response(200, json={"accepted": 1, "duplicates": 0})
        return httpx.Response(404)

    settings = AgentSettings(
        server_url="https://ncc.example.test",
        token=SecretStr("ncc_agent_super-secret"),
        data_dir=tmp_path,
    )
    buffer = TelemetryBuffer(tmp_path / "queue.sqlite3", max_points=100)
    buffer.append({"cpu": {"percent": 12.5}}, datetime.now(timezone.utc))
    client = AgentClient(
        settings,
        "ncc-12345678-1234-4234-8234-123456789abc",
        buffer,
        transport=httpx.MockTransport(handler),
        agent_version="0.6.0-beta.1",
    )

    assert client.enroll() == 14
    client.heartbeat()
    assert client.flush() == 1
    assert json.loads(requests[0].content)["agent_version"] == "0.6.0-beta.1"
    assert json.loads(requests[1].content)["agent_version"] == "0.6.0-beta.1"
    assert buffer.count() == 0
    assert all(request.headers["authorization"] == "Bearer ncc_agent_super-secret" for request in requests)
    assert "super-secret" not in repr(settings)
    client.close()
    buffer.close()


def test_failed_upload_stays_in_offline_buffer(tmp_path: Path) -> None:
    settings = AgentSettings(
        server_url="https://ncc.example.test",
        token=SecretStr("ncc_agent_test"),
        data_dir=tmp_path,
    )
    buffer = TelemetryBuffer(tmp_path / "queue.sqlite3", max_points=100)
    buffer.append({"memory": {"percent": 50}})
    client = AgentClient(
        settings,
        "ncc-12345678-1234-4234-8234-123456789abc",
        buffer,
        transport=httpx.MockTransport(lambda _: httpx.Response(503)),
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.flush()
    assert buffer.count() == 1
    client.close()
    buffer.close()


def test_plain_http_requires_explicit_trusted_network_opt_in(tmp_path: Path) -> None:
    settings = AgentSettings(
        server_url="http://100.100.100.10:8350",
        token=SecretStr("ncc_agent_test"),
        data_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="must use HTTPS"):
        settings.validated_server_url()
    allowed = settings.model_copy(update={"allow_insecure_http": True})
    assert allowed.validated_server_url() == "http://100.100.100.10:8350"
    lookalike = settings.model_copy(update={"server_url": "http://localhost.evil.example"})
    with pytest.raises(ValueError, match="must use HTTPS"):
        lookalike.validated_server_url()


def test_agent_to_server_telemetry_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / "server.db"
    database = Database(f"sqlite+pysqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        issued = issue_agent_token(session, "Roundtrip Agent", utc_now() + timedelta(hours=1))
        plaintext = issued.plaintext

    server = create_app(
        ServerSettings(database_url=f"sqlite+pysqlite:///{database_path.as_posix()}"),
        database,
    )
    buffer = TelemetryBuffer(tmp_path / "agent-buffer.sqlite3", max_points=100)
    buffer.append({"cpu": {"percent": 33.3}})
    machine_id = "ncc-12345678-1234-4234-8234-123456789abc"

    with TestClient(server) as server_client:
        def forward(request: httpx.Request) -> httpx.Response:
            response = server_client.request(
                request.method,
                request.url.path,
                headers={"Authorization": request.headers["authorization"]},
                json=json.loads(request.content),
            )
            return httpx.Response(response.status_code, json=response.json())

        agent = AgentClient(
            AgentSettings(
                server_url="https://ncc.example.test",
                token=SecretStr(plaintext),
                data_dir=tmp_path,
            ),
            machine_id,
            buffer,
            transport=httpx.MockTransport(forward),
        )
        assert agent.enroll() == 10
        agent.heartbeat()
        assert agent.flush() == 1
        agent.close()

    reopened = Database(f"sqlite+pysqlite:///{database_path.as_posix()}")
    with reopened.session() as session:
        point = session.query(TelemetryPoint).one()
        assert point.payload == {"cpu": {"percent": 33.3}}
        assert point.node_id
        assert point.sample_id
    reopened.dispose()
    buffer.close()
