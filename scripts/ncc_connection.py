from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from scripts.ncc_token import DEFAULT_ENV, read_token


def normalize_server_url(target: str, default_port: int = 8350) -> str:
    value = target.strip().rstrip("/")
    if not value:
        raise ValueError("Serveradresse fehlt.")
    if "://" not in value:
        value = f"http://{value}"
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Erwartet wird eine IP, ein MagicDNS-Name oder eine HTTP(S)-URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Die Serveradresse darf keine Zugangsdaten, Query oder Fragment enthalten.")
    if parsed.path not in {"", "/"}:
        raise ValueError("Die Serveradresse darf keinen URL-Pfad enthalten.")
    try:
        port = parsed.port or default_port
    except ValueError as error:
        raise ValueError("Der Port in der Serveradresse ist ungültig.") from error
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return urlunsplit((parsed.scheme, f"{host}:{port}", "", "", ""))


def check_connection(server_url: str, token: str, timeout: float = 8.0) -> dict[str, object]:
    if not token:
        raise ValueError("Kein NCC_TOKEN konfiguriert.")
    request = Request(
        f"{normalize_server_url(server_url)}/api/auth/check",
        headers={"X-NCC-Token": token, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - user-selected NCC host
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise RuntimeError(
                "Token abgelehnt. Importiere die ncc-token-transfer.txt vom Server."
            ) from error
        raise RuntimeError(f"Server antwortet mit HTTP {error.code}.") from error
    except URLError as error:
        reason = getattr(error, "reason", error)
        raise RuntimeError(
            f"Server nicht erreichbar ({reason}). Prüfe Tailscale, Zieladresse und TCP-Port 8350."
        ) from error
    if not isinstance(payload, dict) or payload.get("authorized") is not True:
        raise RuntimeError("Die Antwort stammt nicht von einem kompatiblen NCC-Server.")
    if payload.get("mode") != "server":
        raise RuntimeError(
            f"Das Ziel läuft im Modus {payload.get('mode', 'unbekannt')!r}, nicht im Server-Modus."
        )
    return payload


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="NCC-Clientverbindung normalisieren und prüfen")
    result.add_argument("--env", type=Path, default=DEFAULT_ENV)
    commands = result.add_subparsers(dest="command", required=True)
    normalize = commands.add_parser("normalize")
    normalize.add_argument("target")
    check = commands.add_parser("check")
    check.add_argument("target")
    return result


def main() -> int:
    args = parser().parse_args()
    url = normalize_server_url(args.target)
    if args.command == "normalize":
        print(url)
        return 0
    token = os.environ.get("NCC_TOKEN", "") or read_token(args.env)
    payload = check_connection(url, token)
    print(
        f"Verbindung erfolgreich: {url} "
        f"(NCC {payload.get('version', '?')}, Modus {payload.get('mode', '?')})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"[FEHLER] {error}", file=sys.stderr)
        raise SystemExit(2) from None
