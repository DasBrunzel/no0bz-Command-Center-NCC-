"""Run the NCC agent from Windows Task Scheduler without pywin32 service hosting."""

from __future__ import annotations

import logging
import os
import sys

from ncc_service.environment import load_environment_file
from ncc_service.windows import service_root


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments != ["agent"]:
        raise SystemExit("usage: python -m ncc_service.task_runner agent")

    root = service_root()
    os.environ.update(load_environment_file(root / "config" / "agent.env"))
    log_path = root / "logs" / "agent.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("NCC Agent started through Windows Task Scheduler")
    from ncc_agent.main import main as agent_main

    agent_main()


if __name__ == "__main__":
    main()
