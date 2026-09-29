from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Any

from ncc.config import ROOT

BATCH_SECONDS = 5.0
MAX_MEMORY_POINTS = 86400


class MetricsStore:
    def __init__(self, retention_hours: int) -> None:
        self.retention_hours = retention_hours
        self._lock = threading.Lock()
        self._pending: list[dict[str, Any]] = []
        self._memory: deque[dict[str, Any]] = deque(maxlen=MAX_MEMORY_POINTS)
        self._duckdb: Any | None = None
        self._connection: Any | None = None
        try:
            import duckdb  # type: ignore[import-not-found]

            self._duckdb = duckdb
            self._connection = duckdb.connect(str(ROOT / "no0bz_metrics.duckdb"))
            self._connection.execute("CREATE TABLE IF NOT EXISTS metrics(ts DOUBLE, node_id VARCHAR, payload JSON)")
        except (ImportError, OSError, RuntimeError):
            self._duckdb = None
            self._connection = None

    @property
    def backend(self) -> str:
        return "duckdb" if self._connection is not None else "memory"

    def enqueue(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            self._pending.append(snapshot)

    def flush(self) -> None:
        with self._lock:
            batch, self._pending = self._pending, []
        if not batch:
            return
        if self._connection is None:
            self._memory.extend(batch)
            return
        rows = [(float(item["timestamp"]), str(item["node_id"]), json.dumps(item)) for item in batch]
        self._connection.executemany("INSERT INTO metrics VALUES (?, ?, ?)", rows)

    def cleanup(self) -> None:
        cutoff = time.time() - self.retention_hours * 3600
        if self._connection is not None:
            self._connection.execute("DELETE FROM metrics WHERE ts < ?", [cutoff])
        with self._lock:
            self._memory = deque((item for item in self._memory if float(item["timestamp"]) >= cutoff), maxlen=MAX_MEMORY_POINTS)

    def history(self, minutes: int, max_points: int = 1000) -> list[dict[str, Any]]:
        self.flush()
        cutoff = time.time() - minutes * 60
        if self._connection is not None:
            rows = self._connection.execute("SELECT payload FROM metrics WHERE ts >= ? ORDER BY ts", [cutoff]).fetchall()
            values = [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in rows]
        else:
            with self._lock:
                values = [item for item in self._memory if float(item["timestamp"]) >= cutoff]
        if len(values) <= max_points:
            return values
        stride = max(1, len(values) // max_points)
        return values[::stride][:max_points]

    def close(self) -> None:
        self.flush()
        if self._connection is not None:
            self._connection.close()


class TelemetryRecorder:
    def __init__(self, store: MetricsStore, snapshot_getter: Any, interval: float) -> None:
        self.store = store
        self.snapshot_getter = snapshot_getter
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="ncc-storage", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=BATCH_SECONDS + 1)
        self.store.close()

    def _run(self) -> None:
        next_flush = time.monotonic() + BATCH_SECONDS
        next_cleanup = time.monotonic() + 3600
        while not self._stop.wait(self.interval):
            self.store.enqueue(self.snapshot_getter())
            now = time.monotonic()
            if now >= next_flush:
                self.store.flush()
                next_flush = now + BATCH_SECONDS
            if now >= next_cleanup:
                self.store.cleanup()
                next_cleanup = now + 3600

