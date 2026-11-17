"""Private distribution of the NCC Android app through the NCC server.

The commander uploads a signed APK in the dashboard; paired phones see the
newer version code and install it. Android itself refuses an update that is
not signed with the same key as the installed app, so the server only has to
store the file and describe it (version, size, SHA-256).
"""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from ncc_server.schemas import AndroidReleaseResponse

MAX_APK_BYTES = 150 * 1024 * 1024
APK_NAME = "ncc-android.apk"
META_NAME = "release.json"
_VERSION_NAME = re.compile(r"^[0-9A-Za-z.+_-]{1,32}$")
_ZIP_MAGIC = b"PK\x03\x04"


def current_release(directory: Path) -> AndroidReleaseResponse | None:
    meta = directory / META_NAME
    if not meta.is_file() or not (directory / APK_NAME).is_file():
        return None
    try:
        return AndroidReleaseResponse.model_validate(json.loads(meta.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def apk_path(directory: Path) -> Path:
    return directory / APK_NAME


def store_release(
    directory: Path,
    upload: UploadFile,
    version_code: int,
    version_name: str,
    notes: str,
) -> AndroidReleaseResponse:
    if version_code < 1:
        raise HTTPException(status_code=422, detail="version code must be positive")
    if not _VERSION_NAME.match(version_name):
        raise HTTPException(status_code=422, detail="invalid version name")
    previous = current_release(directory)
    if previous is not None and version_code <= previous.version_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"version code must be higher than the current {previous.version_code}",
        )
    directory.mkdir(parents=True, exist_ok=True)
    partial = directory / f"{APK_NAME}.part"
    digest = hashlib.sha256()
    size = 0
    try:
        with partial.open("wb") as target:
            first = True
            while chunk := upload.file.read(1024 * 1024):
                if first and not chunk.startswith(_ZIP_MAGIC):
                    raise HTTPException(status_code=422, detail="file is not an APK")
                first = False
                size += len(chunk)
                if size > MAX_APK_BYTES:
                    raise HTTPException(status_code=413, detail="APK exceeds 150 MiB")
                digest.update(chunk)
                target.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="file is empty")
        release = AndroidReleaseResponse(
            version_code=version_code,
            version_name=version_name,
            size=size,
            sha256=digest.hexdigest(),
            notes=notes.strip()[:2000],
            uploaded_at=datetime.now(timezone.utc),
        )
        partial.replace(directory / APK_NAME)
        (directory / META_NAME).write_text(release.model_dump_json(), encoding="utf-8")
        return release
    finally:
        with suppress(OSError):
            partial.unlink(missing_ok=True)
