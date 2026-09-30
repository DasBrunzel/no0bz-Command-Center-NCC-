from __future__ import annotations

from ncc_server.dashboard_token import generate_dashboard_token


def test_dashboard_tokens_are_random_and_sufficiently_long() -> None:
    first = generate_dashboard_token()
    second = generate_dashboard_token()
    assert first != second
    assert len(first) >= 40
    assert len(second) >= 40
