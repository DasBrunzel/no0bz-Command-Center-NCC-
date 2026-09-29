from __future__ import annotations

import ipaddress
import re
import shutil
import socket
import subprocess
import sys
from contextlib import suppress

TAILSCALE_RANGE = ipaddress.ip_network("100.64.0.0/10")


def valid(value: str) -> str | None:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    return str(address) if address.version == 4 and address in TAILSCALE_RANGE else None


def command_candidates() -> list[list[str]]:
    commands: list[list[str]] = []
    executable = shutil.which("tailscale")
    if executable:
        commands.append([executable, "ip", "-4"])
    if sys.platform == "win32":
        commands.append(["ipconfig"])
    else:
        commands.extend([["ip", "-4", "addr"], ["hostname", "-I"]])
    return commands


def detect() -> str | None:
    for command in command_candidates():
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=8, shell=False, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        for candidate in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", result.stdout):
            address = valid(candidate)
            if address:
                return address
    with_socket: set[str] = set()
    with suppress(OSError):
        with_socket = {str(item[4][0]) for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    return next((address for candidate in with_socket if (address := valid(candidate))), None)


if __name__ == "__main__":
    address = detect()
    if not address:
        print("Keine aktive Tailscale-IPv4-Adresse gefunden.", file=sys.stderr)
        raise SystemExit(1)
    print(address)
