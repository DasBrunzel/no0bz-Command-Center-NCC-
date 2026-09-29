from __future__ import annotations

import json
import os
import statistics
import time

import psutil
from ncc.collectors.registry import ProviderRegistry
from ncc.config import get_settings

ITERATIONS = 10


def main() -> None:
    registry = ProviderRegistry(get_settings())
    process = psutil.Process(os.getpid())
    durations = []
    process.cpu_percent(None)
    for _ in range(ITERATIONS):
        started = time.perf_counter()
        registry.collect()
        durations.append((time.perf_counter() - started) * 1000)
    result = {
        "iterations": ITERATIONS,
        "collector_mean_ms": round(statistics.mean(durations), 2),
        "collector_p95_ms": round(sorted(durations)[int(ITERATIONS * 0.95) - 1], 2),
        "process_rss_mb": round(process.memory_info().rss / 1024**2, 2),
        "process_cpu_percent": process.cpu_percent(None),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

