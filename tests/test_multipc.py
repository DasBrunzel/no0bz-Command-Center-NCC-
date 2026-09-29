from __future__ import annotations

import time

from ncc.multipc.server import NODE_TIMEOUT_SECONDS, NodeRegistry


def test_node_registration_and_offline_detection() -> None:
    registry = NodeRegistry()
    registry.register("node-1", "Gaming PC")
    host = {"node_id": "host", "timestamp": time.time(), "metrics": {}}
    assert registry.list(host)[1]["online"] is True
    registry._nodes["node-1"]["last_seen"] -= NODE_TIMEOUT_SECONDS + 1
    assert registry.list(host)[1]["online"] is False

