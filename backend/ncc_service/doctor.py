from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def validate_url(value: str, allow_insecure_http: bool) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("invalid NCC server URL")
    if parsed.scheme == "https":
        return normalized
    if parsed.hostname in {"127.0.0.1", "::1", "localhost"} or allow_insecure_http:
        return normalized
    raise ValueError("remote NCC URLs must use HTTPS unless --allow-insecure-http is set")


def run_checks(
    role: str,
    server_url: str,
    token: str,
    *,
    tailscale: bool = False,
    allow_insecure_http: bool = False,
    verify_tls: bool = True,
    transport: httpx.BaseTransport | None = None,
) -> list[CheckResult]:
    url = validate_url(server_url, allow_insecure_http)
    host = urlsplit(url).hostname or ""
    results = [_dns_check(host, tailscale)]
    headers: dict[str, str] = {}
    if token:
        header = "Authorization" if role == "agent" else "X-NCC-Dashboard-Token"
        headers[header] = f"Bearer {token}" if role == "agent" else token
    with httpx.Client(timeout=8, verify=verify_tls, transport=transport) as client:
        results.append(_request_check(client, f"{url}/api/v1/status/live", {}, "API erreichbar"))
        results.append(_request_check(client, f"{url}/api/v1/status/ready", {}, "Datenbank bereit"))
        if role == "agent":
            results.append(
                _request_check(client, f"{url}/api/v1/nodes/me", headers, "Agent-Token")
            )
        else:
            results.append(
                _request_check(
                    client,
                    f"{url}/api/v1/fleet/summary",
                    headers,
                    "Dashboard-Zugang",
                )
            )
    return results


def _dns_check(host: str, require_tailscale: bool) -> CheckResult:
    try:
        addresses = sorted({str(item[4][0]) for item in socket.getaddrinfo(host, None)})
    except OSError as exc:
        return CheckResult("Namensauflösung", False, str(exc))
    if require_tailscale:
        tailscale_network = ipaddress.ip_network("100.64.0.0/10")
        matching = [
            address
            for address in addresses
            if ipaddress.ip_address(address).version == 4
            and ipaddress.ip_address(address) in tailscale_network
        ]
        if not matching:
            return CheckResult(
                "Tailscale-Adresse",
                False,
                f"{host} löst nicht in den Tailscale-Bereich 100.64.0.0/10 auf",
            )
        return CheckResult("Tailscale-Adresse", True, ", ".join(matching))
    return CheckResult("Namensauflösung", True, ", ".join(addresses))


def _request_check(
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    name: str,
) -> CheckResult:
    try:
        response = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return CheckResult(name, False, str(exc))
    if response.is_success:
        return CheckResult(name, True, f"HTTP {response.status_code}")
    if response.status_code == 401:
        detail = "HTTP 401 – Token fehlt oder wurde abgelehnt"
    elif response.status_code == 409 and name == "Agent-Token":
        detail = "HTTP 409 – Token ist gültig, aber noch keinem Agenten zugeordnet"
    else:
        detail = f"HTTP {response.status_code}"
    return CheckResult(name, False, detail)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ncc-doctor",
        description="Prüft NCC Server-, Agent- und Tailscale-Verbindungen ohne Änderungen.",
    )
    parser.add_argument("role", choices=["agent", "server"])
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--token", default=os.environ.get("NCC_DOCTOR_TOKEN", ""))
    parser.add_argument("--tailscale", action="store_true")
    parser.add_argument("--allow-insecure-http", action="store_true")
    parser.add_argument("--no-verify-tls", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        results = run_checks(
            args.role,
            args.server_url,
            args.token,
            tailscale=args.tailscale,
            allow_insecure_http=args.allow_insecure_http,
            verify_tls=not args.no_verify_tls,
        )
    except ValueError as exc:
        print(f"[FEHLER] {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False))
    else:
        for result in results:
            marker = "OK" if result.ok else "FEHLER"
            print(f"[{marker:6}] {result.name}: {result.detail}")
    return 0 if all(result.ok for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
