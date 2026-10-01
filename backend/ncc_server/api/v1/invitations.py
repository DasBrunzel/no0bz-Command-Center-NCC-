from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from ncc.security import limited
from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.agent_tokens import agent_token_is_expired, issue_agent_token, revoke_agent_token
from ncc_server.auth import database_session, require_dashboard_access
from ncc_server.models import AgentToken, Node, utc_now
from ncc_server.schemas import (
    AgentInvitationCreatedResponse,
    AgentInvitationCreateRequest,
    AgentInvitationResponse,
)

router = APIRouter(
    prefix="/agent-invitations",
    tags=["agent invitations"],
    dependencies=[Depends(require_dashboard_access)],
)


@router.get("", response_model=list[AgentInvitationResponse])
async def invitations(
    session: Session = Depends(database_session),
) -> list[AgentInvitationResponse]:
    records = session.scalars(
        select(AgentToken)
        .where(AgentToken.revoked_at.is_(None))
        .order_by(AgentToken.created_at.desc())
    ).all()
    return [_response(session, record) for record in records]


@router.post(
    "",
    response_model=AgentInvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limited("v1-agent-invitations-create", 30))],
)
async def create_invitation(
    payload: AgentInvitationCreateRequest,
    session: Session = Depends(database_session),
) -> AgentInvitationCreatedResponse:
    expires_at = None if payload.expires_hours == 0 else utc_now() + timedelta(hours=payload.expires_hours)
    issued = issue_agent_token(
        session,
        payload.name,
        expires_at,
        actor_type="dashboard",
    )
    return AgentInvitationCreatedResponse(**_response(session, issued.record).model_dump(), token=issued.plaintext)


@router.post(
    "/{token_id}/revoke",
    response_model=AgentInvitationResponse,
    dependencies=[Depends(limited("v1-agent-invitations-revoke", 30))],
)
async def revoke_invitation(
    token_id: str,
    session: Session = Depends(database_session),
) -> AgentInvitationResponse:
    if not revoke_agent_token(session, token_id, actor_type="dashboard"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent invitation not found")
    record = session.get(AgentToken, token_id)
    if record is None:  # pragma: no cover - guarded by revoke_agent_token above
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent invitation not found")
    return _response(session, record)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_revoked_invitation(
    token_id: str,
    session: Session = Depends(database_session),
) -> None:
    record = session.get(AgentToken, token_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent invitation not found")
    if record.revoked_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="revoke an invitation before removing it from the list",
        )
    session.delete(record)
    session.commit()


def _response(session: Session, record: AgentToken) -> AgentInvitationResponse:
    node = session.get(Node, record.node_id) if record.node_id else None
    if record.revoked_at is not None:
        invitation_status: Literal["ready", "bound", "expired", "revoked"] = "revoked"
    elif agent_token_is_expired(record):
        invitation_status = "expired"
    elif record.node_id is not None:
        invitation_status = "bound"
    else:
        invitation_status = "ready"
    return AgentInvitationResponse(
        token_id=record.id,
        name=record.name,
        status=invitation_status,
        node_id=record.node_id,
        node_name=node.display_name if node is not None else None,
        created_at=record.created_at,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
    )
