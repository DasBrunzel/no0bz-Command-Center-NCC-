from __future__ import annotations

import os
import uuid
from contextlib import suppress
from pathlib import Path


def load_or_create_machine_id(data_dir: Path) -> str:
    data_dir.mkdir(parents=True, exist_ok=True)
    with suppress(PermissionError):
        os.chmod(data_dir, 0o700)
    path = data_dir / "machine-id"
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise ValueError(f"Invalid NCC agent identity file: {path}") from exc
        return f"ncc-{parsed}"

    value = str(uuid.uuid4())
    temporary = path.with_suffix(".tmp")
    temporary.write_text(f"{value}\n", encoding="utf-8")
    with suppress(PermissionError):
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    return f"ncc-{value}"
