from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from ncc_server.config import get_server_settings

from ncc_service.environment import load_environment_file


def upgrade(config_path: Path, alembic_path: Path) -> None:
    environment = load_environment_file(config_path, {})
    previous = {key: os.environ.get(key) for key in environment}
    try:
        os.environ.update(environment)
        get_server_settings.cache_clear()
        configuration = Config(str(alembic_path))
        script_location = Path(configuration.get_main_option("script_location") or "migrations")
        if not script_location.is_absolute():
            configuration.set_main_option(
                "script_location", str((alembic_path.parent / script_location).resolve())
            )
        configuration.set_main_option("prepend_sys_path", "")
        command.upgrade(configuration, "head")
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_server_settings.cache_clear()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply NCC database migrations")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--alembic", type=Path, required=True)
    args = parser.parse_args()
    upgrade(args.config, args.alembic)
