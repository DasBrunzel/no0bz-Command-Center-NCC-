from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from ncc.config import ROOT
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_ENV_FILE = ROOT / "ncc-agent.env"


def default_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "no0bz" / "NCC Agent"
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "ncc-agent"


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=AGENT_ENV_FILE,
        env_prefix="NCC_AGENT_",
        extra="ignore",
    )

    server_url: str = ""
    token: SecretStr = SecretStr("")
    data_dir: Path = Field(default_factory=default_data_dir)
    display_name: str = Field(default="", max_length=128)
    collection_interval_seconds: float = Field(default=5.0, ge=1.0, le=300.0)
    heartbeat_interval_seconds: float = Field(default=10.0, ge=5.0, le=300.0)
    request_timeout_seconds: float = Field(default=10.0, ge=1.0, le=120.0)
    batch_size: int = Field(default=25, ge=1, le=100)
    max_buffer_points: int = Field(default=10_000, ge=100, le=1_000_000)
    verify_tls: bool = True
    allow_insecure_http: bool = False
    demo: bool = False

    def validated_server_url(self) -> str:
        value = self.server_url.strip().rstrip("/")
        parsed = urlsplit(value)
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("NCC_AGENT_SERVER_URL is not a valid NCC server base URL")
        if parsed.scheme == "https":
            return value
        if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}:
            return value
        if parsed.scheme == "http" and self.allow_insecure_http:
            return value
        raise ValueError(
            "NCC_AGENT_SERVER_URL must use HTTPS; for trusted Tailscale HTTP set "
            "NCC_AGENT_ALLOW_INSECURE_HTTP=1"
        )
