from __future__ import annotations

import ipaddress
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from pathlib import Path

from fastapi import Depends, Header, HTTPException, Request, WebSocket, status

from ncc.config import Settings, get_settings

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
PROTECTED_PROCESS_NAMES = {
    "system", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "init", "systemd", "kthreadd",
}


def is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def token_matches(candidate: str | None, settings: Settings) -> bool:
    if candidate is None or not candidate:
        return False
    return secrets.compare_digest(candidate, settings.token)


def require_token(
    request: Request,
    authorization: str | None = Header(default=None),
    x_ncc_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.mode == "local" and settings.allow_loopback_no_token and is_loopback(request.client.host if request.client else None):
        return
    bearer = authorization.removeprefix("Bearer ") if authorization else None
    if not token_matches(x_ncc_token or bearer, settings):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid NCC token")


def websocket_authorized(websocket: WebSocket, settings: Settings) -> bool:
    host = websocket.client.host if websocket.client else None
    if settings.mode == "local" and settings.allow_loopback_no_token and is_loopback(host):
        return True
    return token_matches(websocket.query_params.get("token"), settings)


def validate_basename(filename: str) -> str:
    if not filename or filename != Path(filename).name or ".." in filename or any(char in filename for char in ("/", "\\", "\x00")):
        raise HTTPException(status_code=400, detail="Invalid filename: basename required")
    return filename


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            events.append(now)


rate_limiter = RateLimiter()


def limited(action: str, limit: int) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        rate_limiter.check(f"{action}:{client}", limit)

    return dependency

