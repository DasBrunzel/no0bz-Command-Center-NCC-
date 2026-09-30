from __future__ import annotations

import hmac
import ipaddress
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from ncc_server.agent_tokens import find_valid_agent_token
from ncc_server.models import AgentToken


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


def require_dashboard_access(
    request: Request,
    authorization: str | None = Header(default=None),
    x_ncc_dashboard_token: str | None = Header(default=None),
) -> None:
    settings = request.app.state.server_settings
    configured = settings.dashboard_token.get_secret_value()
    supplied = x_ncc_dashboard_token or _bearer_token(authorization) or ""
    if configured and supplied and hmac.compare_digest(configured, supplied):
        return
    client_host = request.client.host if request.client else ""
    if settings.dashboard_allow_loopback_without_token and _is_loopback(client_host):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing or invalid dashboard token",
        headers={"WWW-Authenticate": "Bearer"},
    )


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
