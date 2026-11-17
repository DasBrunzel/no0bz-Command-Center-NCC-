"""Fleet chat and fleet overview for app nodes (the NCC Android app), authenticated by their agent token.

A paired device reads and writes the same Fleet chat as the dashboard. Its
messages carry the node as sender; if the device belongs to a dashboard
account, they are also attributed to that account. The same identity decides
which devices the app may list.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from ncc.security import limited
from sqlalchemy.orm import Session

from ncc_server.access import visible_node_ids
from ncc_server.api.v1.chat import attachment_response, publish_chat_message
from ncc_server.auth import DashboardIdentity, DashboardRole, database_session, require_agent_token
from ncc_server.chat_service import (
    create_chat_message,
    find_chat_attachment,
    list_chat_messages,
    list_chat_participants,
)
from ncc_server.fleet_service import list_fleet_nodes
from ncc_server.models import AgentToken, Node, User
from ncc_server.node_service import TokenNotEnrolledError, bound_node
from ncc_server.schemas import (
    FleetChatMessageCreateRequest,
    FleetChatMessageResponse,
    FleetChatParticipantResponse,
    FleetNodeResponse,
)

router = APIRouter(
    prefix="/nodes/chat",
    tags=["agents"],
    dependencies=[Depends(limited("v1-node-chat", 120))],
)
fleet_router = APIRouter(
    prefix="/nodes",
    tags=["agents"],
    dependencies=[Depends(limited("v1-node-fleet", 120))],
)


def chat_node(
    token: AgentToken = Depends(require_agent_token),
    session: Session = Depends(database_session),
) -> Node:
    try:
        node = bound_node(session, token)
    except TokenNotEnrolledError as exc:
        raise HTTPException(status_code=409, detail="agent token is not enrolled") from exc
    if not node.approved:
        raise HTTPException(status_code=403, detail="node is not approved")
    return node


def _identity(session: Session, node: Node) -> DashboardIdentity:
    """The chat identity a device writes with: its owner's account, else its own name."""
    owner = session.get(User, node.owner_user_id) if node.owner_user_id else None
    if owner is not None and owner.active:
        return DashboardIdentity(owner.id, owner.username, cast(DashboardRole, owner.role))
    return DashboardIdentity(None, node.display_name, cast(DashboardRole, node.access_role))


@fleet_router.get("/fleet", response_model=list[FleetNodeResponse])
async def fleet(
    request: Request,
    node: Node = Depends(chat_node),
    session: Session = Depends(database_session),
) -> list[FleetNodeResponse]:
    """The devices this app may see: all for a commander's phone, a friend's own otherwise."""
    identity = _identity(session, node)
    return list_fleet_nodes(session, request.app.state.server_settings, visible_node_ids(session, identity))


@router.get("/messages", response_model=list[FleetChatMessageResponse])
async def messages(
    limit: int = 100,
    before: str | None = None,
    after: str | None = None,
    _: Node = Depends(chat_node),
    session: Session = Depends(database_session),
) -> list[FleetChatMessageResponse]:
    return list_chat_messages(session, max(1, min(limit, 500)), before=before, after=after)


@router.get("/participants", response_model=list[FleetChatParticipantResponse])
async def participants(
    node: Node = Depends(chat_node), session: Session = Depends(database_session)
) -> list[FleetChatParticipantResponse]:
    return list_chat_participants(session, _identity(session, node))


@router.post("/messages", response_model=FleetChatMessageResponse, status_code=201)
async def send_message(
    payload: FleetChatMessageCreateRequest,
    request: Request,
    node: Node = Depends(chat_node),
    session: Session = Depends(database_session),
) -> FleetChatMessageResponse:
    message = create_chat_message(
        session,
        identity=_identity(session, node),
        body=payload.body,
        body_format=payload.body_format,
        sender_node_id=node.id,
    )
    publish_chat_message(request, message)
    return message


@router.post("/uploads", response_model=FleetChatMessageResponse, status_code=201)
async def send_attachment(
    request: Request,
    file: UploadFile = File(...),
    body: str = Form(default="", max_length=20_000),
    body_format: str = Form(default="plain"),
    node: Node = Depends(chat_node),
    session: Session = Depends(database_session),
) -> FleetChatMessageResponse:
    if body_format not in {"plain", "markdown"}:
        raise HTTPException(status_code=422, detail="unsupported message format")
    message = create_chat_message(
        session,
        identity=_identity(session, node),
        body=body,
        body_format=body_format,
        attachment=file,
        settings=request.app.state.server_settings,
        sender_node_id=node.id,
    )
    publish_chat_message(request, message)
    return message


@router.get("/messages/{message_id}/attachment")
async def attachment(
    message_id: str, _: Node = Depends(chat_node), session: Session = Depends(database_session)
) -> FileResponse:
    result = find_chat_attachment(session, message_id)
    if result is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    return attachment_response(*result)
