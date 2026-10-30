"""Personal dashboard accounts; legacy one-time codes remain valid."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from ncc.security import limited
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ncc_server.auth import (
    DASHBOARD_ROLES,
    DashboardIdentity,
    database_session,
    require_commander_access,
    require_dashboard_identity,
)
from ncc_server.models import (
    AccountInvite,
    AuditEvent,
    DashboardSession,
    Node,
    TelegramLink,
    User,
    utc_now,
)
from ncc_server.schemas import (
    AccountInviteCreatedResponse,
    AccountInviteCreateRequest,
    AccountInviteResponse,
    AccountRegisterRequest,
    DashboardUserCreateRequest,
    DashboardUserLoginRequest,
    DashboardUserPasswordRequest,
    DashboardUserResponse,
    DashboardUserUpdateRequest,
    TelegramAccountResponse,
    TelegramAccountUpdateRequest,
    TelegramLinkCodeResponse,
)
from ncc_server.telegram import telegram_bot_available
from ncc_server.telegram_bot import bot_username, create_link_code, unlink_user
from ncc_server.user_passwords import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["dashboard users"])


def _response(user: User, device_count: int = 0) -> DashboardUserResponse:
    return DashboardUserResponse(
        user_id=user.id, username=user.username, role=cast(Literal["commander", "beta_tester", "friend"], user.role),
        active=user.active, managed=True, created_at=user.created_at,
        full_statistics=user.full_statistics, device_count=device_count,
    )


def _start_session(session: Session, response: Response, user: User) -> None:
    raw = secrets.token_urlsafe(32)
    session.add(DashboardSession(user_id=user.id, token_hash=_digest(raw), expires_at=utc_now() + timedelta(days=30)))
    response.set_cookie("ncc_dashboard_session", raw, httponly=True, samesite="strict", max_age=60 * 60 * 24 * 30)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.get("/me", response_model=DashboardUserResponse)
async def me(identity: DashboardIdentity = Depends(require_dashboard_identity)) -> DashboardUserResponse:
    return DashboardUserResponse(
        user_id=identity.user_id, username=identity.username,
        role=identity.access_role, active=True, managed=identity.user_id is not None,
        full_statistics=identity.full_statistics,
    )


def _personal_account(identity: DashboardIdentity) -> str:
    if identity.user_id is None:
        raise HTTPException(status_code=403, detail="a personal account is required")
    return identity.user_id


@router.get("/me/telegram", response_model=TelegramAccountResponse)
async def my_telegram(
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> TelegramAccountResponse:
    settings = request.app.state.server_settings
    link = session.scalar(select(TelegramLink).where(TelegramLink.user_id == identity.user_id)) if identity.user_id else None
    return TelegramAccountResponse(
        available=telegram_bot_available(settings) and identity.user_id is not None,
        linked=link is not None,
        telegram_name=link.telegram_name if link else None,
        weekly_recap=link.weekly_recap if link else True,
        bot_username=await bot_username(settings),
    )


@router.post("/me/telegram/link", response_model=TelegramLinkCodeResponse,
             dependencies=[Depends(limited("telegram-link-code", 10))])
async def create_telegram_link(
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> TelegramLinkCodeResponse:
    user_id = _personal_account(identity)
    settings = request.app.state.server_settings
    if not telegram_bot_available(settings):
        raise HTTPException(status_code=503, detail="Telegram ist auf dem Server nicht eingerichtet")
    code, expires = create_link_code(session, user_id)
    username = await bot_username(settings)
    return TelegramLinkCodeResponse(code=code, expires_at=expires, deep_link=f"https://t.me/{username}?start={code}" if username else None)


@router.patch("/me/telegram", response_model=TelegramAccountResponse)
async def update_my_telegram(
    payload: TelegramAccountUpdateRequest,
    request: Request,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> TelegramAccountResponse:
    user_id = _personal_account(identity)
    link = session.scalar(select(TelegramLink).where(TelegramLink.user_id == user_id))
    if link is None:
        raise HTTPException(status_code=404, detail="no Telegram chat linked")
    link.weekly_recap = payload.weekly_recap
    session.commit()
    return await my_telegram(request, identity, session)


@router.delete("/me/telegram", status_code=204)
async def unlink_my_telegram(
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> None:
    unlink_user(session, _personal_account(identity))


@router.get("", response_model=list[DashboardUserResponse], dependencies=[Depends(require_commander_access)])
async def list_users(session: Session = Depends(database_session)) -> list[DashboardUserResponse]:
    counts = dict(session.execute(
        select(Node.owner_user_id, func.count()).where(Node.owner_user_id.is_not(None)).group_by(Node.owner_user_id)
    ).all())
    return [_response(user, counts.get(user.id, 0)) for user in session.scalars(select(User).order_by(User.username)).all()]


@router.get("/invites", response_model=list[AccountInviteResponse], dependencies=[Depends(require_commander_access)])
async def list_invites(session: Session = Depends(database_session)) -> list[AccountInviteResponse]:
    invites = session.scalars(select(AccountInvite).order_by(AccountInvite.created_at.desc()).limit(50)).all()
    return [_invite_response(session, invite) for invite in invites]


@router.post("/invites", response_model=AccountInviteCreatedResponse, status_code=201,
             dependencies=[Depends(require_commander_access), Depends(limited("account-invite-create", 20))])
async def create_invite(
    payload: AccountInviteCreateRequest,
    identity: DashboardIdentity = Depends(require_dashboard_identity),
    session: Session = Depends(database_session),
) -> AccountInviteCreatedResponse:
    # Grouped for reading aloud or typing on a phone, e.g. "K7QP-2MXD-9RTB".
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(12))
    code = "-".join(raw[index:index + 4] for index in range(0, 12, 4))
    invite = AccountInvite(
        label=payload.label.strip(), code_hash=_invite_digest(code), created_by=identity.user_id,
        expires_at=utc_now() + timedelta(days=payload.expires_days),
    )
    session.add(invite)
    session.flush()
    session.add(AuditEvent(actor_type="dashboard-user", actor_id=identity.user_id, action="account-invite.created",
                           details=json.dumps({"invite_id": invite.id, "label": invite.label})))
    session.commit()
    return AccountInviteCreatedResponse(**_invite_response(session, invite).model_dump(), code=code)


@router.post("/invites/{invite_id}/revoke", response_model=AccountInviteResponse, dependencies=[Depends(require_commander_access)])
async def revoke_invite(invite_id: str, session: Session = Depends(database_session)) -> AccountInviteResponse:
    invite = session.get(AccountInvite, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="invite not found")
    if invite.used_at is None and invite.revoked_at is None:
        invite.revoked_at = utc_now()
        session.add(AuditEvent(actor_type="dashboard-user", action="account-invite.revoked", details=json.dumps({"invite_id": invite.id})))
        session.commit()
    return _invite_response(session, invite)


@router.post("/register", response_model=DashboardUserResponse, status_code=201,
             dependencies=[Depends(limited("dashboard-user-register", 10))])
async def register(
    payload: AccountRegisterRequest, response: Response, session: Session = Depends(database_session),
) -> DashboardUserResponse:
    """Create a friend account from a commander's invite and sign it in."""
    invite = session.scalar(select(AccountInvite).where(AccountInvite.code_hash == _invite_digest(payload.code)))
    if invite is None or invite.used_at is not None or invite.revoked_at is not None or _as_utc(invite.expires_at) <= utc_now():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invite code is invalid or expired")
    username = payload.username.strip().lower()
    if session.scalar(select(User.id).where(User.username == username)):
        raise HTTPException(status_code=409, detail="username already exists")
    user = User(username=username, password_hash=hash_password(payload.password), role="friend", active=True)
    session.add(user)
    session.flush()
    invite.used_at, invite.used_by = utc_now(), user.id
    session.add(AuditEvent(actor_type="dashboard-user", actor_id=user.id, action="user.registered",
                           details=json.dumps({"invite_id": invite.id})))
    _start_session(session, response, user)
    session.commit()
    return _response(user)


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
    if payload.full_statistics is not None:
        user.full_statistics = payload.full_statistics
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
        action="user.updated", details=json.dumps({"user_id": user.id, "role": user.role, "active": user.active, "full_statistics": user.full_statistics}),
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
    if user is None or not user.active or user.role not in DASHBOARD_ROLES or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")
    _start_session(session, response, user)
    session.commit()
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


def _invite_digest(code: str) -> str:
    # Codes are typed by people; ignore case, spaces and dashes.
    return _digest("".join(character for character in code.upper() if character.isalnum()))


def _invite_response(session: Session, invite: AccountInvite) -> AccountInviteResponse:
    if invite.used_at is not None:
        invite_status: Literal["open", "used", "expired", "revoked"] = "used"
    elif invite.revoked_at is not None:
        invite_status = "revoked"
    elif _as_utc(invite.expires_at) <= utc_now():
        invite_status = "expired"
    else:
        invite_status = "open"
    user = session.get(User, invite.used_by) if invite.used_by else None
    return AccountInviteResponse(
        invite_id=invite.id, label=invite.label, created_at=invite.created_at, expires_at=invite.expires_at,
        status=invite_status, used_by=user.username if user else None,
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
