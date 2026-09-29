from __future__ import annotations

import time

from ncc.storage.db import MetricsStore


def test_memory_history(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    store = MetricsStore(24)
    if store._connection is not None:
        store._connection.close()
    store._connection = None
    store.enqueue({"timestamp": time.time(), "node_id": "test", "metrics": {"cpu": 10}})
    points = store.history(1)
    assert points[0]["node_id"] == "test"

