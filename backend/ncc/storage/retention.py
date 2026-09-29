from __future__ import annotations

from ncc.storage.db import MetricsStore


def run_retention(store: MetricsStore) -> None:
    """Run the scheduled retention pass (kept separate for testability)."""
    store.cleanup()

