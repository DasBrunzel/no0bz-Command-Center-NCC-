from __future__ import annotations

import socket
import sys
from pathlib import Path

import httpx
import pytest
from ncc_server.config import ServerSettings
from ncc_service.doctor import main as doctor_main
from ncc_service.doctor import run_checks, validate_url
from ncc_service.environment import load_environment_file
from ncc_service.migrate import upgrade
from ncc_service.process import child_python_executable
from sqlalchemy import create_engine, text


def test_service_environment_file_is_loaded_without_replacing_base(tmp_path: Path) -> None:
    config = tmp_path / "agent.env"
    config.write_text(
        "# NCC service\nNCC_AGENT_SERVER_URL=\"https://ncc.example\"\n"
        "NCC_AGENT_TOKEN='secret-token'\nDATA_DIR=\"C:\\\\ProgramData\\\\no0bz\"\nEMPTY=\n",
        encoding="utf-8",
    )
    result = load_environment_file(config, {"PATH": "test-path"})
    assert result["PATH"] == "test-path"
    assert result["NCC_AGENT_SERVER_URL"] == "https://ncc.example"
    assert result["NCC_AGENT_TOKEN"] == "secret-token"
    assert result["DATA_DIR"] == r"C:\ProgramData\no0bz"
    assert result["EMPTY"] == ""


def test_service_environment_rejects_malformed_lines(tmp_path: Path) -> None:
    config = tmp_path / "bad.env"
    config.write_text("NOT AN ENV LINE\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid environment entry"):
        load_environment_file(config)


def test_service_migration_uses_external_environment_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "service.db"
    config = tmp_path / "server.env"
    config.write_text(
        f'NCC_SERVER_DATABASE_URL="sqlite+pysqlite:///{database_path.as_posix()}"\n',
        encoding="utf-8",
    )
    alembic_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    monkeypatch.chdir(tmp_path)
    upgrade(config, alembic_path)
    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "20261003_0008"
        assert connection.execute(text("SELECT COUNT(*) FROM nodes")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM fleet_groups")).scalar_one() == 0
    engine.dispose()


def test_doctor_checks_server_and_tailscale(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(*_: object) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.100.10.20", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/fleet/summary":
            assert request.headers["X-NCC-Dashboard-Token"] == "dashboard-secret"
        return httpx.Response(200, json={"status": "ok"})

    results = run_checks(
        "server",
        "http://ncc.tailnet.ts.net:8350",
        "dashboard-secret",
        tailscale=True,
        allow_insecure_http=True,
        transport=httpx.MockTransport(handler),
    )
    assert len(results) == 4
    assert all(result.ok for result in results)
    assert results[0].name == "Tailscale-Adresse"


def test_doctor_reports_rejected_agent_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        status = 401 if request.url.path == "/api/v1/nodes/me" else 200
        return httpx.Response(status, json={})

    results = run_checks(
        "agent",
        "http://localhost:8350",
        "wrong",
        transport=httpx.MockTransport(handler),
    )
    assert [result.ok for result in results] == [True, True, True, False]
    assert "Token" in results[-1].detail


def test_doctor_rejects_remote_plain_http_and_supports_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        validate_url("http://192.0.2.10:8350", allow_insecure_http=False)
    code = doctor_main(
        ["server", "--server-url", "not-a-url", "--token", "secret", "--json"]
    )
    assert code == 2
    assert "invalid NCC server URL" in capsys.readouterr().err


def test_service_packaging_contains_safe_defaults() -> None:
    root = Path(__file__).resolve().parents[1]
    agent = (root / "packaging/systemd/ncc-agent.service").read_text(encoding="utf-8")
    server = (root / "packaging/systemd/ncc-server.service").read_text(encoding="utf-8")
    assert "Restart=on-failure" in agent
    assert "NoNewPrivileges=true" in agent
    assert "EnvironmentFile=/etc/ncc/agent.env" in agent
    assert "ExecStartPre=" in server
    assert "User=ncc" in server
    assert "NCC_AGENT_TOKEN" not in agent
    assert "NCC_SERVER_DASHBOARD_TOKEN" not in server


def test_linux_agent_installer_can_explicitly_replace_existing_credentials() -> None:
    root = Path(__file__).resolve().parents[1]
    installer = (root / "scripts/install_ncc_agent_service.sh").read_text(encoding="utf-8")
    assert "--replace-config" in installer
    assert '[ "$replace_config" -eq 1 ]' in installer


def test_windows_agent_installer_can_preselect_a_tailscale_server() -> None:
    root = Path(__file__).resolve().parents[1]
    installer = (root / "scripts/install_ncc_service.ps1").read_text(encoding="utf-8")
    assert "[string]$ServerUrl" in installer
    assert "[switch]$ReplaceConfig" in installer
    assert "$target = $ServerUrl" in installer


def test_windows_agent_installer_supports_task_scheduler_fallback() -> None:
    root = Path(__file__).resolve().parents[1]
    installer = (root / "scripts/install_ncc_service.ps1").read_text(encoding="utf-8")
    runner = (root / "backend/ncc_service/task_runner.py").read_text(encoding="utf-8")
    assert '[string]$AgentMode = "Service"' in installer
    assert "ncc_service.task_runner agent" in installer
    assert "Browser-Freigabe: $configuredServerUrl/?pair=$pairingId" in installer
    assert "NCC Agent started through Windows Task Scheduler" in runner


def test_unraid_configuration_reads_key_without_printing_it() -> None:
    root = Path(__file__).resolve().parents[1]
    setup = (root / "scripts/configure_ncc_unraid.ps1").read_text(encoding="utf-8")
    assert "Read-Host \"Unraid API-Key" in setup
    assert '"x-api-key" = $apiKey' in setup
    assert "NCC_SERVER_UNRAID_API_KEY" in setup
    assert "Write-Host $apiKey" not in setup


def test_unraid_settings_support_legacy_setup_key_names() -> None:
    settings = ServerSettings(
        NCC_UNRAID_URL="http://100.88.247.35/graphql",
        NCC_UNRAID_API_KEY="secret",
        NCC_UNRAID_DISPLAY_NAME="horsttower",
    )
    assert settings.unraid_url == "http://100.88.247.35/graphql"
    assert settings.unraid_api_key.get_secret_value() == "secret"


def test_unraid_schema_inspection_does_not_export_api_key() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts/inspect_ncc_unraid_schema.ps1").read_text(encoding="utf-8")
    assert "__schema" in script
    assert "ncc-unraid-schema.json" in script
    assert "apiKey" not in script.split("Write-Host", maxsplit=1)[1]


def test_service_host_launches_the_venv_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service_host = tmp_path / "pythonservice.exe"
    interpreter = tmp_path / "Scripts" / "python.exe"
    interpreter.parent.mkdir()
    service_host.touch()
    interpreter.touch()
    monkeypatch.setattr(sys, "executable", str(service_host))
    assert child_python_executable() == str(interpreter)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows service host test")
def test_windows_service_uses_importable_class_name(monkeypatch: pytest.MonkeyPatch) -> None:
    from ncc_service import windows

    captured: dict[str, object] = {}

    def handle(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(windows.win32serviceutil, "HandleCommandLine", handle)
    windows.main(["agent", "debug"])
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["serviceClassString"] == "ncc_service.windows.AgentWindowsService"
    assert kwargs["argv"] == [sys.argv[0], "debug"]
