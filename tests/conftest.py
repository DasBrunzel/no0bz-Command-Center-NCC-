from __future__ import annotations

from collections.abc import Iterator

import pytest
from ncc.security import rate_limiter


@pytest.fixture(autouse=True)
def fresh_rate_limits() -> Iterator[None]:
    """Each test starts with empty rate limits; the limiter is process-wide."""
    rate_limiter.reset()
    yield
