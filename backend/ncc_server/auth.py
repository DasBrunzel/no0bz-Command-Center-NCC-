from __future__ import annotations

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


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, separator, credentials = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and credentials:
        return credentials
    return None
