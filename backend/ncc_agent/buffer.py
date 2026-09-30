from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BufferedTelemetry:
    row_id: int
    sample_id: str
    recorded_at: str
    metrics: dict[str, object]


class TelemetryBuffer:
    def __init__(self, path: Path, max_points: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with suppress(PermissionError):
            os.chmod(path.parent, 0o700)
        self.max_points = max_points
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(path, check_same_thread=False)
        with suppress(PermissionError):
            os.chmod(path, 0o600)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS telemetry_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT NOT NULL UNIQUE,
                recorded_at TEXT NOT NULL,
                metrics_json TEXT NOT NULL
            )"""
        )
        self._connection.commit()

    def append(
        self,
        metrics: dict[str, object],
        recorded_at: datetime | None = None,
    ) -> str:
        sample_id = str(uuid.uuid4())
        moment = recorded_at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        timestamp = moment.astimezone(timezone.utc).isoformat()
        payload = json.dumps(metrics, separators=(",", ":"), ensure_ascii=False)
        with self._lock:
            self._connection.execute(
                "INSERT INTO telemetry_queue(sample_id, recorded_at, metrics_json) VALUES (?, ?, ?)",
                (sample_id, timestamp, payload),
            )
            overflow = self.count_unlocked() - self.max_points
            if overflow > 0:
                self._connection.execute(
                    "DELETE FROM telemetry_queue WHERE id IN "
                    "(SELECT id FROM telemetry_queue ORDER BY id LIMIT ?)",
                    (overflow,),
                )
            self._connection.commit()
        return sample_id

    def peek(self, limit: int) -> list[BufferedTelemetry]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, sample_id, recorded_at, metrics_json "
                "FROM telemetry_queue ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            BufferedTelemetry(
                row_id=int(row[0]),
                sample_id=str(row[1]),
                recorded_at=str(row[2]),
                metrics=json.loads(str(row[3])),
            )
            for row in rows
        ]

    def acknowledge(self, row_ids: list[int]) -> None:
        if not row_ids:
            return
        with self._lock:
            self._connection.executemany(
                "DELETE FROM telemetry_queue WHERE id = ?",
                ((row_id,) for row_id in row_ids),
            )
            self._connection.commit()

    def count(self) -> int:
        with self._lock:
            return self.count_unlocked()

    def count_unlocked(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) FROM telemetry_queue").fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        with self._lock:
            self._connection.close()
