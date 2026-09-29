from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="NCC_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = Field(default=8350, ge=1, le=65535)
    token: str = ""
    mode: Literal["local", "server", "client"] = "local"
    server_url: str = ""
    upload_max_mb: int = Field(default=25, ge=1, le=2048)
    upload_total_mb: int = Field(default=512, ge=1, le=16384)
    retention_hours: int = Field(default=24, ge=1, le=8760)
    interval: float = Field(default=1.0, ge=0.25, le=60.0)
    lhm_url: HttpUrl = HttpUrl("http://127.0.0.1:8085/data.json")
    demo: bool = False
    allow_loopback_no_token: bool = True

    @property
    def uploads_dir(self) -> Path:
        return ROOT / "ncc_uploads"


def ensure_env() -> str:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("NCC_TOKEN="):
                return line.partition("=")[2]
    token = secrets.token_urlsafe(32)
    source = (ROOT / ".env.example").read_text(encoding="utf-8")
    ENV_FILE.write_text(source.replace("NCC_TOKEN=\n", f"NCC_TOKEN={token}\n"), encoding="utf-8")
    print(f"NCC first-start token: {token}")
    return token


@lru_cache
def get_settings() -> Settings:
    token = ensure_env()
    settings = Settings()
    if not settings.token:
        settings.token = token
    settings.uploads_dir.mkdir(exist_ok=True)
    return settings

