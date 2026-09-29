from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any, cast

from ncc.collectors.base import Capabilities, SensorProvider
from ncc.collectors.system import (
    DemoProvider,
    LibreHardwareMonitorProvider,
    LinuxAmdGpuProvider,
    LinuxHwmonProvider,
    NvidiaProvider,
    PsutilProvider,
    SmartctlProvider,
    WindowsGpuProvider,
)
from ncc.config import ROOT, Settings

PROVIDER_TIMEOUT_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 300.0


class ProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        providers: list[SensorProvider] = (
            [DemoProvider()]
            if settings.demo
            else [
                PsutilProvider(),
                WindowsGpuProvider(),
                LinuxAmdGpuProvider(),
                NvidiaProvider(),
                LibreHardwareMonitorProvider(str(settings.lhm_url)),
                SmartctlProvider(),
                LinuxHwmonProvider(),
            ]
        )
        self.providers = sorted(providers, key=lambda item: item.priority)
        self.capabilities: list[Capabilities] = [provider.probe() for provider in self.providers]
        self._failures: dict[str, int] = {}
        self._paused_until: dict[str, float] = {}
        self._pool = ThreadPoolExecutor(max_workers=max(2, len(providers)), thread_name_prefix="ncc-provider")

    def collect(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        now = time.monotonic()
        for provider in self.providers:
            if not provider.is_available() or self._paused_until.get(provider.name, 0) > now:
                continue
            try:
                values = self._pool.submit(provider.collect).result(timeout=PROVIDER_TIMEOUT_SECONDS)
                merged.update(values)
                self._failures[provider.name] = 0
            except (Exception, TimeoutError):
                count = self._failures.get(provider.name, 0) + 1
                self._failures[provider.name] = count
                self._paused_until[provider.name] = now + min(2**count, MAX_BACKOFF_SECONDS)
        return merged


class SnapshotCollector:
    def __init__(self, registry: ProviderRegistry, interval: float, node_id: str) -> None:
        self.registry = registry
        self.interval = interval
        self.node_id = node_id
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] = {"node_id": node_id, "timestamp": time.time(), "metrics": {}}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="ncc-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval + 1)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return cast(dict[str, Any], json.loads(json.dumps(self._snapshot)))

    def _run(self) -> None:
        while not self._stop.is_set():
            snapshot = {"node_id": self.node_id, "timestamp": time.time(), "metrics": self.registry.collect()}
            with self._lock:
                self._snapshot = snapshot
            self._stop.wait(self.interval)


def save_hardware_cache(registry: ProviderRegistry, static_data: dict[str, Any]) -> Path:
    path = ROOT / "ncc_system_cache.json"
    payload = {"static": static_data, "providers": [capability.__dict__ if hasattr(capability, "__dict__") else {"provider": capability.provider, "available": capability.available, "metrics": capability.metrics, "reason": capability.reason, "hint": capability.hint} for capability in registry.capabilities]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path

