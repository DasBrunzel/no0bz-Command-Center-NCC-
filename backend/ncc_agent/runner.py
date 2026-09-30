from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from ncc.collectors.registry import ProviderRegistry, SnapshotCollector
from ncc.config import Settings as CollectorSettings

from ncc_agent.buffer import TelemetryBuffer
from ncc_agent.client import AgentClient, AgentRejectedError
from ncc_agent.config import AgentSettings
from ncc_agent.identity import load_or_create_machine_id

logger = logging.getLogger(__name__)
MAX_BACKOFF_SECONDS = 60.0


class AgentRunner:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.machine_id = load_or_create_machine_id(settings.data_dir)
        self.buffer = TelemetryBuffer(
            settings.data_dir / "telemetry-buffer.sqlite3",
            settings.max_buffer_points,
        )
        collector_settings = CollectorSettings(
            token="agent-internal",
            mode="local",
            interval=settings.collection_interval_seconds,
            demo=settings.demo,
        )
        self.registry = ProviderRegistry(collector_settings)
        self.collector = SnapshotCollector(
            self.registry,
            settings.collection_interval_seconds,
            self.machine_id,
        )
        self.client = AgentClient(settings, self.machine_id, self.buffer)
        self.stop_event = threading.Event()

    def run(self) -> int:
        self.collector.start()
        enrolled = False
        backoff = 1.0
        next_network_attempt = 0.0
        heartbeat_interval = self.settings.heartbeat_interval_seconds
        logger.info("NCC Agent %s started as %s", self.machine_id, self.settings.display_name or "host")
        try:
            while not self.stop_event.wait(self.settings.collection_interval_seconds):
                snapshot = self.collector.snapshot()
                self.buffer.append(
                    _metrics(snapshot),
                    datetime.fromtimestamp(float(snapshot["timestamp"]), timezone.utc),
                )
                if time.monotonic() < next_network_attempt:
                    continue
                try:
                    if not enrolled:
                        heartbeat_interval = float(self.client.enroll())
                        enrolled = True
                    self.client.heartbeat()
                    sent = self.client.flush()
                    if sent:
                        logger.info("Sent %d telemetry point(s); %d buffered", sent, self.buffer.count())
                    backoff = 1.0
                    next_network_attempt = time.monotonic() + heartbeat_interval
                except AgentRejectedError as exc:
                    logger.error("NCC Agent authentication/enrollment failed: %s", exc)
                    return 2
                except (httpx.HTTPError, OSError) as exc:
                    logger.warning(
                        "NCC Server unavailable; %d point(s) buffered; retry in %.0fs: %s",
                        self.buffer.count(),
                        backoff,
                        exc,
                    )
                    enrolled = False
                    next_network_attempt = time.monotonic() + backoff
                    backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
        finally:
            self.collector.stop()
            self.client.close()
            self.buffer.close()
        return 0

    def stop(self) -> None:
        self.stop_event.set()


def _metrics(snapshot: dict[str, Any]) -> dict[str, object]:
    metrics = snapshot.get("metrics", {})
    return metrics if isinstance(metrics, dict) else {}
