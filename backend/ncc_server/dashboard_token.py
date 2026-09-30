from __future__ import annotations

import secrets


def generate_dashboard_token() -> str:
    return secrets.token_urlsafe(32)


def main() -> None:
    print("Dashboard token created. Store it as NCC_SERVER_DASHBOARD_TOKEN:")
    print(generate_dashboard_token())
