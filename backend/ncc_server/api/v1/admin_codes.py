import hashlib
import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from ncc.security import limited
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ncc_server.auth import database_session, require_dashboard_access
from ncc_server.models import AdminCode, AuditEvent, DashboardSession, utc_now
from ncc_server.schemas import (
    AdminCodeCreatedResponse,
    AdminCodeCreateRequest,
    AdminCodeRedeemRequest,
    AdminCodeResponse,
)

router = APIRouter(prefix="/admin-codes", tags=["admin codes"])


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@router.post(
    "",
    response_model=AdminCodeCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_dashboard_access), Depends(limited("admin-code-create", 10))],
)
async def create(
    payload: AdminCodeCreateRequest,
    session: Session = Depends(database_session),
) -> AdminCodeCreatedResponse:
    code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    expires = utc_now() + timedelta(minutes=payload.expires_minutes)
    record = AdminCode(
        label=" ".join(payload.label.split()),
        code_hash=digest(code),
        expires_at=expires,
    )
    session.add(record)
    session.flush()
    session.add(
        AuditEvent(
            actor_type="dashboard",
            action="admin-code.created",
            details=json.dumps({"code_id": record.id, "label": record.label}),
        )
    )
    session.commit()
    return AdminCodeCreatedResponse(code=code, expires_at=expires)


@router.get("", response_model=list[AdminCodeResponse], dependencies=[Depends(require_dashboard_access)])
async def list_codes(
    session: Session = Depends(database_session),
) -> list[AdminCodeResponse]:
    records = session.scalars(select(AdminCode).order_by(AdminCode.created_at.desc())).all()
    return [_response(record) for record in records]


@router.post("/redeem", dependencies=[Depends(limited("admin-code-redeem", 10))])
async def redeem(
    payload: AdminCodeRedeemRequest,
    response: Response,
    session: Session = Depends(database_session),
) -> dict[str, str]:
    now = utc_now()
    record = session.scalar(select(AdminCode).where(AdminCode.code_hash == digest(payload.code)))
    if record is None or record.used_at or record.revoked_at or _as_utc(record.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired admin code")
    record.used_at = now
    raw = secrets.token_urlsafe(32)
    session.add(DashboardSession(code_id=record.id, token_hash=digest(raw), expires_at=now + timedelta(days=30)))
    session.commit()
    response.set_cookie(
        "ncc_dashboard_session",
        raw,
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 30,
    )
    return {"status": "ok"}


@router.post(
    "/{code_id}/revoke",
    response_model=AdminCodeResponse,
    dependencies=[Depends(require_dashboard_access)],
)
async def revoke(
    code_id: str,
    session: Session = Depends(database_session),
) -> AdminCodeResponse:
    record = session.get(AdminCode, code_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="admin code not found")
    if record.revoked_at is None:
        record.revoked_at = utc_now()
        session.execute(
            update(DashboardSession)
            .where(DashboardSession.code_id == record.id)
            .where(DashboardSession.revoked_at.is_(None))
            .values(revoked_at=record.revoked_at)
        )
        session.add(
            AuditEvent(
                actor_type="dashboard",
                action="admin-code.revoked",
                details=json.dumps({"code_id": record.id, "label": record.label}),
            )
        )
        session.commit()
    return _response(record)


def _response(record: AdminCode) -> AdminCodeResponse:
    now = utc_now()
    if record.revoked_at is not None:
        state: Literal["ready", "used", "expired", "revoked"] = "revoked"
    elif record.used_at is not None:
        state = "used"
    elif _as_utc(record.expires_at) <= now:
        state = "expired"
    else:
        state = "ready"
    return AdminCodeResponse(
        code_id=record.id,
        label=record.label,
        status=state,
        created_at=record.created_at,
        expires_at=record.expires_at,
        used_at=record.used_at,
        revoked_at=record.revoked_at,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
