from __future__ import annotations

import json
from pathlib import Path

import pytest
from ncc_payload import __version__
from ncc_payload.main import _health_path, _write_health


def test_payload_writes_secret_free_health_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NCC_CORE_STATE_DIR", str(tmp_path))
    _write_health("ready")
    assert json.loads((tmp_path / "payload-health.json").read_text(encoding="utf-8")) == {
        "payload_version": __version__,
        "status": "ready",
    }


def test_payload_requires_core_state_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NCC_CORE_STATE_DIR", raising=False)
    with pytest.raises(ValueError, match="NCC_CORE_STATE_DIR"):
        _health_path()
