from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from ncc.models import utc_now

MAX_MESSAGES = 1000
chat_lock = threading.Lock()
_messages: deque[dict[str, Any]] = deque(maxlen=MAX_MESSAGES)


def add_message(sender: str, text: str, kind: str) -> dict[str, Any]:
    message = {"id": f"msg-{time.time_ns()}", "timestamp": utc_now().isoformat(), "sender": sender, "text": text, "kind": kind}
    with chat_lock:
        _messages.append(message)
    return message


def list_messages() -> list[dict[str, Any]]:
    with chat_lock:
        return list(_messages)

