from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.auth import database_session, require_dashboard_access
from ncc_server.chat_service import (
    create_chat_message,
    find_chat_attachment,
    list_chat_messages,
    list_chat_participants,
)
from ncc_server.schemas import (
    FleetChatMessageCreateRequest,
    FleetChatMessageResponse,
    FleetChatParticipantResponse,
)

router = APIRouter(
    prefix="/fleet/chat",
    tags=["fleet chat"],
    dependencies=[Depends(require_dashboard_access), Depends(limited("fleet-chat", 120))],
)


@router.get("/messages", response_model=list[FleetChatMessageResponse])
async def messages(limit: int = 100, session: Session = Depends(database_session)) -> list[FleetChatMessageResponse]:
    return list_chat_messages(session, max(1, min(limit, 500)))


@router.get("/participants", response_model=list[FleetChatParticipantResponse])
async def participants(request: Request, session: Session = Depends(database_session)) -> list[FleetChatParticipantResponse]:
    return list_chat_participants(session, request.app.state.server_settings)


@router.post("/messages", response_model=FleetChatMessageResponse, status_code=201)
async def send_message(
    payload: FleetChatMessageCreateRequest,
    session: Session = Depends(database_session),
) -> FleetChatMessageResponse:
    return create_chat_message(
        session,
        sender_node_id=payload.sender_node_id,
        body=payload.body,
        body_format=payload.body_format,
    )


@router.post("/uploads", response_model=FleetChatMessageResponse, status_code=201)
async def send_attachment(
    request: Request,
    file: UploadFile = File(...),
    sender_node_id: str | None = Form(default=None),
    body: str = Form(default=""),
    body_format: str = Form(default="plain"),
    session: Session = Depends(database_session),
) -> FleetChatMessageResponse:
    if body_format not in {"plain", "markdown"}:
        raise HTTPException(status_code=422, detail="unsupported message format")
    return create_chat_message(
        session,
        sender_node_id=sender_node_id or None,
        body=body,
        body_format=body_format,
        attachment=file,
        settings=request.app.state.server_settings,
    )


@router.get("/messages/{message_id}/attachment")
async def attachment(message_id: str, session: Session = Depends(database_session)) -> FileResponse:
    result = find_chat_attachment(session, message_id)
    if result is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    message, path = result
    if not path.is_file():
        raise HTTPException(status_code=404, detail="attachment file not found")
    return FileResponse(path, media_type=message.attachment_type, filename=message.attachment_name)
