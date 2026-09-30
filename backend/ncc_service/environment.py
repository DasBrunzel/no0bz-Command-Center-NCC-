from __future__ import annotations

import os
from pathlib import Path


def load_environment_file(path: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    """Return a child-process environment with values from a simple dotenv file."""
    result = dict(base if base is not None else os.environ)
    if not path.is_file():
        raise FileNotFoundError(f"NCC service configuration not found: {path}")
    for number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key or not key.replace("_", "").isalnum():
            raise ValueError(f"invalid environment entry at {path}:{number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
            if raw_line.partition("=")[2].lstrip().startswith('"'):
                value = value.replace(r'\"', '"').replace(r"\\", "\\")
        result[key] = value
    return result
