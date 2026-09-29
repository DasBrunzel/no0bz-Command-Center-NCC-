from __future__ import annotations

import secrets
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException

from ncc.config import Settings
from ncc.security import validate_basename

CHUNK_SIZE = 1024 * 1024


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.iterdir() if item.is_file())


def save_upload(source: BinaryIO, filename: str, settings: Settings) -> Path:
    clean_name = validate_basename(filename)
    target = settings.uploads_dir / clean_name
    if target.exists():
        target = settings.uploads_dir / f"{secrets.token_hex(4)}-{clean_name}"
    written = 0
    max_file = settings.upload_max_mb * CHUNK_SIZE
    max_total = settings.upload_total_mb * CHUNK_SIZE
    try:
        with target.open("xb") as destination:
            while chunk := source.read(CHUNK_SIZE):
                written += len(chunk)
                if written > max_file:
                    raise HTTPException(status_code=413, detail=f"File exceeds {settings.upload_max_mb} MB limit")
                if directory_size(settings.uploads_dir) + len(chunk) > max_total:
                    raise HTTPException(status_code=413, detail=f"Upload storage exceeds {settings.upload_total_mb} MB limit")
                destination.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target

