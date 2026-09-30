from __future__ import annotations

import logging
import signal

from ncc_agent.config import AgentSettings
from ncc_agent.runner import AgentRunner


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        runner = AgentRunner(AgentSettings())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"NCC Agent configuration error: {exc}") from exc

    def stop_agent(*_: object) -> None:
        runner.stop()

    signal.signal(signal.SIGINT, stop_agent)
    signal.signal(signal.SIGTERM, stop_agent)
    raise SystemExit(runner.run())


if __name__ == "__main__":
    main()
