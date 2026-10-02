from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path


def load_token(data_dir: Path) -> str:
    path = data_dir / "agent-credential.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ""
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid NCC agent credential file: {path}") from exc
    token = value.get("token") if isinstance(value, dict) else None
    return token if isinstance(token, str) else ""


def save_token(data_dir: Path, token: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    temporary = data_dir / "agent-credential.tmp"
    target = data_dir / "agent-credential.json"
    temporary.write_text(json.dumps({"token": token}), encoding="utf-8")
    with suppress(PermissionError):
        os.chmod(temporary, 0o600)
    temporary.replace(target)


def clear_token(data_dir: Path) -> None:
    with suppress(FileNotFoundError):
        (data_dir / "agent-credential.json").unlink()
