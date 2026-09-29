from __future__ import annotations

from pathlib import Path

from scripts.ncc_token import export_token, read_token, write_token
from scripts.tailscale_ip import valid


def test_token_roundtrip_and_export(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    transfer = tmp_path / "transfer.txt"
    token = "a" * 43
    write_token(env, token)
    assert read_token(env) == token
    export_token(transfer, token)
    assert transfer.read_text(encoding="utf-8").strip() == token


def test_token_preserves_other_environment_values(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("NCC_MODE=server\nNCC_TOKEN=old-token-that-is-long-enough-1234\n", encoding="utf-8")
    write_token(env, "b" * 43)
    assert "NCC_MODE=server" in env.read_text(encoding="utf-8")
    assert read_token(env) == "b" * 43


def test_tailscale_address_validation() -> None:
    assert valid("100.64.0.1") == "100.64.0.1"
    assert valid("100.127.255.254") == "100.127.255.254"
    assert valid("100.128.0.1") is None
    assert valid("192.168.1.10") is None
