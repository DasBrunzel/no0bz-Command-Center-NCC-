from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import httpx
from ncc.collectors.registry import ProviderRegistry, SnapshotCollector
from ncc.config import Settings as CollectorSettings

from ncc_agent import __version__
from ncc_agent.buffer import TelemetryBuffer
from ncc_agent.client import AgentClient, AgentRejectedError
from ncc_agent.config import AgentSettings
from ncc_agent.credentials import clear_token, load_token, save_token
from ncc_agent.identity import load_or_create_machine_id

logger = logging.getLogger(__name__)
MAX_BACKOFF_SECONDS = 60.0


class AgentRunner:
    def __init__(
        self,
        settings: AgentSettings,
        *,
        agent_version: str | None = None,
        on_update_check: Callable[[], None] | None = None,
    ) -> None:
        self.settings = settings
        # Only a Core-managed payload can act on a dashboard update request.
        self.on_update_check = on_update_check
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
        self.client = AgentClient(
            settings, self.machine_id, self.buffer,
            agent_version=agent_version or __version__,
        )
        saved_token = load_token(settings.data_dir)
        if saved_token:
            self.client.set_token(saved_token)
        self.stop_event = threading.Event()

    def run(self) -> int:
        self.collector.start()
        enrolled = False
        backoff = 1.0
        next_network_attempt = 0.0
        heartbeat_interval = self.settings.heartbeat_interval_seconds
        last_buffered_generation = 0
        logger.info("NCC Agent %s started as %s", self.machine_id, self.settings.display_name or "host")
        try:
            while not self.stop_event.wait(
                _next_wake_seconds(
                    self.settings.collection_interval_seconds,
                    next_network_attempt,
                    time.monotonic(),
                )
            ):
                snapshot = self.collector.snapshot()
                generation = int(snapshot["generation"])
                snapshot_at = float(snapshot["timestamp"])
                # The collector runs independently from this upload loop. On a
                # busy host the upload loop can read the same snapshot twice.
                # Use collection order rather than wall time, which can move
                # backwards when the system clock is corrected.
                if _is_new_snapshot(generation, last_buffered_generation):
                    self.buffer.append(
                        _metrics(snapshot),
                        datetime.fromtimestamp(snapshot_at, timezone.utc),
                    )
                    last_buffered_generation = generation
                if time.monotonic() < next_network_attempt:
                    continue
                try:
                    if not self.client.has_token:
                        self.client.register_pairing()
                        token = self.client.claim_pairing()
                        if token is None:
                            next_network_attempt = time.monotonic() + 5.0
                            continue
                        save_token(self.settings.data_dir, token)
                        self.client.set_token(token)
                        logger.info("NCC Agent pairing approved; internal credential stored locally")
                    if not enrolled:
                        heartbeat_interval = float(self.client.enroll())
                        enrolled = True
                    if self.client.heartbeat():
                        self._request_update_check()
                    sent = self.client.flush()
                    if sent:
                        logger.info("Sent %d telemetry point(s); %d buffered", sent, self.buffer.count())
                    backoff = 1.0
                    next_network_attempt = time.monotonic() + heartbeat_interval
                except AgentRejectedError as exc:
                    if self.client.has_token and self.settings.pairing_id:
                        logger.warning("NCC Agent credential was rejected; waiting for a new browser approval")
                        clear_token(self.settings.data_dir)
                        self.client.set_token("")
                        enrolled = False
                        next_network_attempt = time.monotonic() + 5.0
                        continue
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

    def _request_update_check(self) -> None:
        if self.on_update_check is None:
            logger.info("Update check requested by the dashboard; this agent has no NCC Core to run it")
            return
        try:
            self.on_update_check()
            logger.info("Update check requested by the dashboard; handed to NCC Core")
        except OSError as exc:
            logger.warning("Could not hand the dashboard update request to NCC Core: %s", exc)


def _is_new_snapshot(generation: int, last_buffered_generation: int) -> bool:
    """Return whether a collector snapshot has not already been queued."""
    return generation > last_buffered_generation


def _next_wake_seconds(
    collection_interval: float, next_network_attempt: float, now: float,
) -> float:
    """Wake for either a new collector sample or the next server attempt."""
    return min(collection_interval, max(0.1, next_network_attempt - now))


def _metrics(snapshot: dict[str, Any]) -> dict[str, object]:
    metrics = snapshot.get("metrics", {})
    return metrics if isinstance(metrics, dict) else {}
