from __future__ import annotations

import pytest
from fastapi import HTTPException
from ncc.config import Settings
from ncc.security import RateLimiter, token_matches, validate_basename


def test_rejects_path_traversal() -> None:
    for name in ("../secret", "..\\secret", "a/b", "a\\b"):
        with pytest.raises(HTTPException):
            validate_basename(name)


def test_token_comparison() -> None:
    settings = Settings(token="correct")
    assert token_matches("correct", settings)
    assert not token_matches("wrong", settings)
    assert not token_matches(None, settings)


def test_rate_limit() -> None:
    limiter = RateLimiter()
    limiter.check("client", 1)
    with pytest.raises(HTTPException) as error:
        limiter.check("client", 1)
    assert error.value.status_code == 429

