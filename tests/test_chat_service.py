from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from ncc_server.auth import DashboardIdentity
from ncc_server.chat_service import create_chat_message
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.models import Base
from starlette.datastructures import Headers, UploadFile


def test_failed_chat_commit_removes_stored_attachment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'chat.db').as_posix()}")
    Base.metadata.create_all(database.engine)
    uploads = tmp_path / "uploads"
    settings = ServerSettings(chat_upload_dir=uploads)
    attachment = UploadFile(file=BytesIO(b"diagnostic data"), filename="diagnose.txt", headers=Headers({"content-type": "text/plain"}))

    with database.session() as session:
        def fail_commit() -> None:
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="database unavailable"):
            create_chat_message(
                session, identity=DashboardIdentity(None, "Commander", "commander"),
                body="", body_format="plain", attachment=attachment, settings=settings,
            )
        assert list(uploads.iterdir()) == []
        assert not session.new
