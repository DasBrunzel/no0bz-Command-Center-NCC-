from __future__ import annotations

import json
import logging
import os
import signal
from pathlib import Path

from ncc_agent.config import AgentSettings
from ncc_agent.runner import AgentRunner

from ncc_payload import __version__


def _health_path() -> Path:
    value = os.environ.get("NCC_CORE_STATE_DIR", "").strip()
    if not value:
        raise ValueError("NCC_CORE_STATE_DIR is required for a 0.6 payload")
    return Path(value) / "payload-health.json"


def _write_health(status: str) -> None:
    path = _health_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"payload_version": __version__, "status": status}, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    runner = AgentRunner(AgentSettings())

    def stop_payload(*_: object) -> None:
        _write_health("stopping")
        runner.stop()

    signal.signal(signal.SIGINT, stop_payload)
    signal.signal(signal.SIGTERM, stop_payload)
    _write_health("ready")
    raise SystemExit(runner.run())


if __name__ == "__main__":
    main()
