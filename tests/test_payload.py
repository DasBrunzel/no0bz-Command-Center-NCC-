from __future__ import annotations

import json
import os
import subprocess
import sys
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


def test_payload_uses_core_supplied_release_version() -> None:
    """A signed staged payload must report the manifest version, not its fallback."""
    environment = dict(os.environ, NCC_PAYLOAD_VERSION="0.6.0-beta.3")
    result = subprocess.run(
        [sys.executable, "-c", "import ncc_payload; print(ncc_payload.__version__)"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "0.6.0-beta.3"
