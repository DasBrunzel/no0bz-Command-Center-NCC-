from __future__ import annotations

import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.auth import DashboardIdentity
from ncc_server.config import ServerSettings
from ncc_server.models import FleetChatMessage, User
from ncc_server.schemas import (
    FleetChatAttachmentResponse,
    FleetChatMessageResponse,
    FleetChatParticipantResponse,
)

MAX_CHAT_ATTACHMENT_BYTES = 100 * 1024 * 1024
_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")


def list_chat_messages(session: Session, limit: int) -> list[FleetChatMessageResponse]:
    rows = session.scalars(
        select(FleetChatMessage).order_by(FleetChatMessage.created_at.desc()).limit(limit)
    ).all()
    return [_message_response(row) for row in reversed(rows)]


def list_chat_participants(
    session: Session, identity: DashboardIdentity
) -> list[FleetChatParticipantResponse]:
    users = session.scalars(select(User).where(User.active.is_(True)).order_by(User.username)).all()
    participants = [
        FleetChatParticipantResponse(
            user_id=user.id,
            display_name=user.username,
            role=user.role,
        )
        for user in users if user.role in {"commander", "beta_tester"}
    ]
    if identity.user_id is None:
        participants.append(FleetChatParticipantResponse(user_id=None, display_name=identity.username, role=identity.access_role))
    return participants


def create_chat_message(
    session: Session,
    *,
    identity: DashboardIdentity,
    body: str,
    body_format: str,
    attachment: UploadFile | None = None,
    settings: ServerSettings | None = None,
) -> FleetChatMessageResponse:
    body = body.rstrip()
    if not body and attachment is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="message is empty")
    message = FleetChatMessage(
        sender_user_id=identity.user_id,
        sender_name=identity.username,
        body=body,
        body_format=body_format,
    )
    if attachment is not None:
        if settings is None:  # pragma: no cover - API always supplies settings
            raise RuntimeError("chat upload settings are required")
        _store_attachment(message, attachment, settings.chat_upload_dir)
    session.add(message)
    session.commit()
    return _message_response(message)


def find_chat_attachment(session: Session, message_id: str) -> tuple[FleetChatMessage, Path] | None:
    message = session.get(FleetChatMessage, message_id)
    if message is None or not message.attachment_path:
        return None
    return message, Path(message.attachment_path)


def _store_attachment(message: FleetChatMessage, upload: UploadFile, upload_dir: Path) -> None:
    original = Path(upload.filename or "Anhang").name
    safe_name = _FILENAME.sub("_", original).strip(" ._") or "Anhang"
    suffix = Path(safe_name).suffix[:16]
    upload_dir.mkdir(parents=True, exist_ok=True)
    relative = f"{uuid.uuid4().hex}{suffix}"
    target = upload_dir / relative
    written = 0
    try:
        with target.open("xb") as destination:
            while chunk := upload.file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_CHAT_ATTACHMENT_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="attachment exceeds the 100 MiB limit",
                    )
                destination.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    message.attachment_name = safe_name[:255]
    message.attachment_path = str(target)
    message.attachment_type = (upload.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream")[:128]
    message.attachment_size = written


def _message_response(message: FleetChatMessage) -> FleetChatMessageResponse:
    attachment = None
    if message.attachment_name and message.attachment_path and message.attachment_size is not None:
        attachment = FleetChatAttachmentResponse(
            name=message.attachment_name,
            content_type=message.attachment_type or "application/octet-stream",
            size=message.attachment_size,
            url=f"/api/v1/fleet/chat/messages/{message.id}/attachment",
        )
    return FleetChatMessageResponse(
        message_id=message.id,
        sender_node_id=message.sender_node_id,
        sender_user_id=message.sender_user_id,
        sender_name=message.sender_name,
        body=message.body,
        body_format=message.body_format,  # type: ignore[arg-type]
        attachment=attachment,
        created_at=message.created_at,
    )
