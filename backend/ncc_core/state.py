from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Health = Literal["inactive", "awaiting_health", "healthy", "rolled_back"]


@dataclass(frozen=True)
class CoreState:
    active_payload: str | None = None
    previous_payload: str | None = None
    last_update: str | None = None
    health: Health = "inactive"

    @classmethod
    def load(cls, path: Path) -> CoreState:
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("invalid NCC Core state file") from exc
        if not isinstance(raw, dict):
            raise ValueError("invalid NCC Core state file")
        active = raw.get("active_payload")
        previous = raw.get("previous_payload")
        last_update = raw.get("last_update")
        health = raw.get("health")
        if (
            active is not None
            and not isinstance(active, str)
            or previous is not None
            and not isinstance(previous, str)
            or last_update is not None
            and not isinstance(last_update, str)
            or health not in {"inactive", "awaiting_health", "healthy", "rolled_back"}
        ):
            raise ValueError("invalid NCC Core state file")
        return cls(active, previous, last_update, health)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
