from __future__ import annotations

import hashlib
import hmac
import ipaddress
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, cast

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.agent_tokens import find_valid_agent_token
from ncc_server.models import AdminCode, AgentToken, DashboardSession, User, utc_now


@dataclass(frozen=True)
class DashboardIdentity:
    user_id: str | None
    username: str
    access_role: Literal["commander", "beta_tester"]


def database_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.database.sessions()


def require_agent_token(
    authorization: str | None = Header(default=None),
    x_ncc_agent_token: str | None = Header(default=None),
    session: Session = Depends(database_session),
) -> AgentToken:
    bearer = _bearer_token(authorization)
    record = find_valid_agent_token(session, x_ncc_agent_token or bearer or "")
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid agent token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return record


def require_dashboard_identity(
    request: Request,
    authorization: str | None = Header(default=None),
    x_ncc_dashboard_token: str | None = Header(default=None),
) -> DashboardIdentity:
    session_token = request.cookies.get("ncc_dashboard_session", "")
    if session_token:
        with request.app.state.database.session() as session:
            browser_session = session.scalar(
                select(DashboardSession)
                .where(DashboardSession.token_hash == hashlib.sha256(session_token.encode()).hexdigest())
                .where(DashboardSession.revoked_at.is_(None))
                .where(DashboardSession.expires_at > utc_now())
            )
            if browser_session is not None:
                if browser_session.user_id:
                    user = session.get(User, browser_session.user_id)
                    if user and user.active and user.role in {"commander", "beta_tester"}:
                        return DashboardIdentity(user.id, user.username, cast(Literal["commander", "beta_tester"], user.role))
                elif browser_session.code_id:
                    code = session.get(AdminCode, browser_session.code_id)
                    if code and code.revoked_at is None and code.access_role in {"commander", "beta_tester"}:
                        return DashboardIdentity(None, code.access_role.replace("_", " ").title(), cast(Literal["commander", "beta_tester"], code.access_role))
    settings = request.app.state.server_settings
    configured = settings.dashboard_token.get_secret_value()
    supplied = x_ncc_dashboard_token or _bearer_token(authorization) or ""
    if configured and supplied and hmac.compare_digest(configured, supplied):
        return DashboardIdentity(None, "Commander", "commander")
    client_host = request.client.host if request.client else ""
    if settings.dashboard_allow_loopback_without_token and _is_loopback(client_host):
        return DashboardIdentity(None, "Commander", "commander")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing or invalid dashboard token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_dashboard_access(
    identity: DashboardIdentity = Depends(require_dashboard_identity),
) -> Literal["commander", "beta_tester"]:
    return identity.access_role


def require_commander_access(
    access_role: Literal["commander", "beta_tester"] = Depends(require_dashboard_access),
) -> Literal["commander"]:
    if access_role != "commander":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="commander access required",
        )
    return "commander"


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, separator, credentials = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and credentials:
        return credentials
    return None


def _is_loopback(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return value.lower() == "localhost"
