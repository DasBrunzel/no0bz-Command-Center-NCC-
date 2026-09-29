from __future__ import annotations

from functools import lru_cache

from ncc.config import ENV_FILE
from pydantic import Field
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


@lru_cache
def get_server_settings() -> ServerSettings:
    return ServerSettings()
