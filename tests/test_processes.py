from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from ncc.api.processes import kill_process


def test_refuses_own_process() -> None:
    with pytest.raises(HTTPException) as error:
        kill_process(os.getpid(), "test")
    assert error.value.status_code == 403

