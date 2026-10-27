"""Personal dashboard accounts; legacy one-time codes remain valid."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from ncc.security import limited
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ncc_server.auth import (
    DashboardIdentity,
    database_session,
    require_commander_access,
    require_dashboard_identity,
)
from ncc_server.models import AuditEvent, DashboardSession, User, utc_now
from ncc_server.schemas import (
    DashboardUserCreateRequest,
    DashboardUserLoginRequest,
    DashboardUserPasswordRequest,
    DashboardUserResponse,
    DashboardUserUpdateRequest,
)
from ncc_server.user_passwords import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["dashboard users"])


def _response(user: User) -> DashboardUserResponse:
    return DashboardUserResponse(
        user_id=user.id, username=user.username, role=user.role,
        active=user.active, managed=True, created_at=user.created_at,
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.get("/me", response_model=DashboardUserResponse)
async def me(identity: DashboardIdentity = Depends(require_dashboard_identity)) -> DashboardUserResponse:
    return DashboardUserResponse(
        user_id=identity.user_id, username=identity.username,
        role=identity.access_role, active=True, managed=identity.user_id is not None,
    )


@router.get("", response_model=list[DashboardUserResponse], dependencies=[Depends(require_commander_access)])
async def list_users(session: Session = Depends(database_session)) -> list[DashboardUserResponse]:
    return [_response(user) for user in session.scalars(select(User).order_by(User.username)).all()]


@router.post("", response_model=DashboardUserResponse, status_code=201, dependencies=[Depends(require_commander_access)])
async def create_user(
    payload: DashboardUserCreateRequest,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> DashboardUserResponse:
    if session.scalar(select(User.id).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role, active=True)
    session.add(user)
    session.flush()
    session.add(AuditEvent(
        actor_type="dashboard-user", actor_id=identity.user_id,
        action="user.created", details=json.dumps({"user_id": user.id, "role": user.role}),
    ))
    session.commit()
    return _response(user)


@router.patch("/{user_id}", response_model=DashboardUserResponse, dependencies=[Depends(require_commander_access)])
async def update_user(
    user_id: str,
    payload: DashboardUserUpdateRequest,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> DashboardUserResponse:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    next_role = payload.role or user.role
    next_active = user.active if payload.active is None else payload.active
    if user.id == identity.user_id and not next_active:
        raise HTTPException(status_code=409, detail="cannot deactivate your own account")
    if user.active and user.role == "commander" and (not next_active or next_role != "commander"):
        commanders = session.scalar(select(func.count()).select_from(User).where(User.active.is_(True), User.role == "commander")) or 0
        if commanders <= 1:
            raise HTTPException(status_code=409, detail="at least one active commander is required")
    user.role, user.active = next_role, next_active
    if not user.active:
        session.execute(update(DashboardSession).where(DashboardSession.user_id == user.id).where(DashboardSession.revoked_at.is_(None)).values(revoked_at=utc_now()))
    session.add(AuditEvent(
        actor_type="dashboard-user", actor_id=identity.user_id,
        action="user.updated", details=json.dumps({"user_id": user.id, "role": user.role, "active": user.active}),
    ))
    session.commit()
    return _response(user)


@router.post("/login", dependencies=[Depends(limited("dashboard-user-login", 10))])
async def login(
    payload: DashboardUserLoginRequest,
    response: Response,
    session: Session = Depends(database_session),
) -> dict[str, str]:
    user = session.scalar(select(User).where(User.username == payload.username.strip().lower()))
    if user is None or not user.active or user.role not in {"commander", "beta_tester"} or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")
    raw = secrets.token_urlsafe(32)
    session.add(DashboardSession(user_id=user.id, token_hash=_digest(raw), expires_at=utc_now() + timedelta(days=30)))
    session.commit()
    response.set_cookie("ncc_dashboard_session", raw, httponly=True, samesite="strict", max_age=60 * 60 * 24 * 30)
    return {"status": "ok"}


@router.post("/password", status_code=204)
async def change_password(
    payload: DashboardUserPasswordRequest,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> None:
    if identity.user_id is None:
        raise HTTPException(status_code=403, detail="a personal account is required")
    user = session.get(User, identity.user_id)
    if user is None or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    current_hash = _digest(request.cookies.get("ncc_dashboard_session", ""))
    session.execute(update(DashboardSession).where(DashboardSession.user_id == user.id).where(DashboardSession.token_hash != current_hash).where(DashboardSession.revoked_at.is_(None)).values(revoked_at=utc_now()))
    session.add(AuditEvent(actor_type="dashboard-user", actor_id=user.id, action="user.password-changed"))
    session.commit()
