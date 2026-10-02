from __future__ import annotations

from functools import lru_cache

from ncc.config import ENV_FILE
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="NCC_SERVER_",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8350, ge=1, le=65535)
    database_url: str = "postgresql+psycopg://ncc:ncc@127.0.0.1:5432/ncc"
    database_check_on_start: bool = True
    heartbeat_interval_seconds: int = Field(default=10, ge=5, le=300)
    node_offline_after_seconds: int = Field(default=30, ge=10, le=3600)
    dashboard_token: SecretStr = SecretStr("")
    dashboard_allow_loopback_without_token: bool = True
    telegram_enabled: bool = False
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""


@lru_cache
def get_server_settings() -> ServerSettings:
    return ServerSettings()
