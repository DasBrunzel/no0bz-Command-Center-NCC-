from __future__ import annotations

import socket
import threading
import time
from typing import Any

NODE_TIMEOUT_SECONDS = 15.0


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register(self, node_id: str, name: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            node = self._nodes.setdefault(node_id, {})
            node.update({"node_id": node_id, "name": name, "profile": profile, "last_seen": time.time()})
            return dict(node)

    def telemetry(self, node_id: str, snapshot: dict[str, Any]) -> None:
        with self._lock:
            node = self._nodes.setdefault(node_id, {"node_id": node_id, "name": node_id})
            node.update({"last_seen": time.time(), "snapshot": snapshot})

    def list(self, host_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        now = time.time()
        host = {"node_id": host_snapshot["node_id"], "name": socket.gethostname(), "last_seen": now, "online": True, "host": True, "snapshot": host_snapshot}
        with self._lock:
            remotes = [dict(value, online=now - float(value.get("last_seen", 0)) <= NODE_TIMEOUT_SECONDS, host=False) for value in self._nodes.values()]
        return [host, *remotes]


nodes = NodeRegistry()

