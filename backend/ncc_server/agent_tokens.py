from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.models import AgentToken, AuditEvent, utc_now

TOKEN_PREFIX = "ncc_agent_"


@dataclass(frozen=True)
class IssuedAgentToken:
    record: AgentToken
    plaintext: str


def hash_agent_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def issue_agent_token(
    session: Session,
    name: str,
    expires_at: datetime | None,
) -> IssuedAgentToken:
    plaintext = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    record = AgentToken(
        name=name,
        token_hash=hash_agent_token(plaintext),
        expires_at=expires_at,
    )
    session.add(record)
    session.flush()
    session.add(
        AuditEvent(
            actor_type="server-cli",
            action="agent-token.created",
            details=json.dumps(
                {"token_id": record.id, "name": name, "expires_at": _iso(expires_at)},
                separators=(",", ":"),
            ),
        )
    )
    session.commit()
    return IssuedAgentToken(record=record, plaintext=plaintext)


def find_valid_agent_token(session: Session, plaintext: str) -> AgentToken | None:
    if not plaintext.startswith(TOKEN_PREFIX) or len(plaintext) > 256:
        return None
    digest = hash_agent_token(plaintext)
    record = session.scalar(select(AgentToken).where(AgentToken.token_hash == digest))
    if record is None or not secrets.compare_digest(record.token_hash, digest):
        return None
    if record.revoked_at is not None:
        return None
    if agent_token_is_expired(record):
        return None
    return record


def agent_token_is_expired(record: AgentToken) -> bool:
    return record.expires_at is not None and _as_utc(record.expires_at) <= utc_now()


def revoke_agent_token(session: Session, token_id: str) -> bool:
    record = session.get(AgentToken, token_id)
    if record is None:
        return False
    if record.revoked_at is None:
        record.revoked_at = utc_now()
        session.add(
            AuditEvent(
                actor_type="server-cli",
                action="agent-token.revoked",
                details=json.dumps({"token_id": record.id}, separators=(",", ":")),
            )
        )
        session.commit()
    return True


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
