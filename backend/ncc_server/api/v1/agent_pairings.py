from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from ncc.security import limited
from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.agent_tokens import issue_agent_token
from ncc_server.auth import database_session, require_dashboard_access
from ncc_server.models import AgentPairing, AgentToken, AuditEvent, Node, utc_now
from ncc_server.schemas import (
    AgentPairingClaimRequest,
    AgentPairingClaimResponse,
    AgentPairingRegisterRequest,
    AgentPairingResponse,
)

router = APIRouter(prefix="/agent-pairings", tags=["agent pairings"])
PAIRING_LIFETIME = timedelta(minutes=15)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@router.post(
    "/register",
    response_model=AgentPairingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limited("v1-agent-pairing-register", 20))],
)
async def register(
    payload: AgentPairingRegisterRequest,
    session: Session = Depends(database_session),
) -> AgentPairingResponse:
    now = utc_now()
    secret_hash = _digest(payload.pairing_secret)
    record = session.get(AgentPairing, payload.pairing_id)
    if record is not None:
        if not hmac.compare_digest(record.secret_hash, secret_hash):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="pairing identifier is unavailable")
        if record.cancelled_at is not None or record.claimed_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="pairing is no longer available")
        return _response(record)
    record = AgentPairing(
        id=payload.pairing_id,
        secret_hash=secret_hash,
        display_name=payload.display_name,
        machine_id=payload.machine_id,
        platform=payload.platform,
        agent_version=payload.agent_version,
        metadata_json=dict(payload.metadata),
        expires_at=now + PAIRING_LIFETIME,
    )
    session.add(record)
    session.add(
        AuditEvent(
            actor_type="agent-pairing",
            actor_id=record.id,
            action="agent-pairing.registered",
            details=json.dumps({"machine_id": record.machine_id}, separators=(",", ":")),
        )
    )
    session.commit()
    return _response(record)


@router.get("", response_model=list[AgentPairingResponse], dependencies=[Depends(require_dashboard_access)])
async def list_pairings(session: Session = Depends(database_session)) -> list[AgentPairingResponse]:
    records = session.scalars(select(AgentPairing).order_by(AgentPairing.created_at.desc())).all()
    return [_response(record) for record in records]


@router.post(
    "/{pairing_id}/approve",
    response_model=AgentPairingResponse,
    dependencies=[Depends(require_dashboard_access), Depends(limited("v1-agent-pairing-approve", 20))],
)
async def approve(pairing_id: str, session: Session = Depends(database_session)) -> AgentPairingResponse:
    record = session.get(AgentPairing, pairing_id)
    if record is None or record.cancelled_at is not None or record.claimed_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pairing request not found")
    if _as_utc(record.expires_at) <= utc_now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="pairing request expired")
    if record.approved_at is None:
        record.approved_at = utc_now()
        session.add(
            AuditEvent(
                actor_type="dashboard",
                actor_id=record.id,
                action="agent-pairing.approved",
                details=json.dumps({"machine_id": record.machine_id}, separators=(",", ":")),
            )
        )
        session.commit()
    return _response(record)


@router.post(
    "/{pairing_id}/claim",
    response_model=AgentPairingClaimResponse,
    dependencies=[Depends(limited("v1-agent-pairing-claim", 30))],
)
async def claim(
    pairing_id: str,
    payload: AgentPairingClaimRequest,
    session: Session = Depends(database_session),
) -> AgentPairingClaimResponse:
    record = session.get(AgentPairing, pairing_id)
    valid_secret = record is not None and hmac.compare_digest(record.secret_hash, _digest(payload.pairing_secret))
    if not valid_secret or record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid pairing request")
    if record.cancelled_at is not None or _as_utc(record.expires_at) <= utc_now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="pairing request expired")
    if record.approved_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="pairing approval is pending")
    if record.claimed_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="pairing was already claimed")
    record.claimed_at = utc_now()
    issued = issue_agent_token(session, record.display_name, None, actor_type="agent-pairing")
    existing_node = session.scalar(select(Node).where(Node.machine_id == record.machine_id))
    if existing_node is not None:
        issued.record.node_id = existing_node.id
        for prior_token in session.scalars(
            select(AgentToken).where(
                AgentToken.node_id == existing_node.id,
                AgentToken.id != issued.record.id,
                AgentToken.revoked_at.is_(None),
            )
        ):
            prior_token.revoked_at = utc_now()
        session.add(
            AuditEvent(
                actor_type="agent-pairing",
                actor_id=record.id,
                action="agent-pairing.rebound",
                details=json.dumps({"node_id": existing_node.id}, separators=(",", ":")),
            )
        )
    session.add(
        AuditEvent(
            actor_type="agent-pairing",
            actor_id=record.id,
            action="agent-pairing.claimed",
            details=json.dumps({"token_id": issued.record.id}, separators=(",", ":")),
        )
    )
    session.commit()
    return AgentPairingClaimResponse(token=issued.plaintext)


def _response(record: AgentPairing) -> AgentPairingResponse:
    now = utc_now()
    if record.cancelled_at is not None:
        pairing_status: Literal["waiting", "approved", "claimed", "expired", "cancelled"] = "cancelled"
    elif record.claimed_at is not None:
        pairing_status = "claimed"
    elif _as_utc(record.expires_at) <= now:
        pairing_status = "expired"
    elif record.approved_at is not None:
        pairing_status = "approved"
    else:
        pairing_status = "waiting"
    return AgentPairingResponse(
        pairing_id=record.id,
        display_name=record.display_name,
        platform=record.platform,
        status=pairing_status,
        created_at=record.created_at,
        expires_at=record.expires_at,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
