from __future__ import annotations

import io

import pytest
from fastapi import HTTPException
from ncc.config import Settings
from ncc.hub.uploads import save_upload


class TempSettings(Settings):
    target: str

    @property
    def uploads_dir(self):  # type: ignore[no-untyped-def]
        from pathlib import Path

        return Path(self.target)


def test_rejects_oversized_upload(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = TempSettings(token="test", upload_max_mb=1, target=str(tmp_path))
    with pytest.raises(HTTPException) as error:
        save_upload(io.BytesIO(b"x" * (1024 * 1024 + 1)), "large.bin", settings)
    assert error.value.status_code == 413


