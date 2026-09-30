from __future__ import annotations

import argparse
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ncc_server.agent_tokens import (
    agent_token_is_expired,
    issue_agent_token,
    revoke_agent_token,
)
from ncc_server.config import get_server_settings
from ncc_server.database import Database
from ncc_server.models import AgentToken, utc_now


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ncc-agent-token",
        description="Create and manage individual NCC agent tokens.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="create a new one-time-visible token")
    create.add_argument("--name", required=True, help="human-readable device/invitation name")
    create.add_argument(
        "--expires-hours",
        type=int,
        default=720,
        help="validity in hours; 0 creates a token without expiry (default: 720)",
    )

    commands.add_parser("list", help="list token metadata without revealing secrets")
    revoke = commands.add_parser("revoke", help="revoke one token immediately")
    revoke.add_argument("token_id", help="token UUID shown by the list command")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    database = Database(get_server_settings().database_url)
    try:
        with database.session() as session:
            if args.command == "create":
                if args.expires_hours < 0 or args.expires_hours > 8760:
                    parser.error("--expires-hours must be between 0 and 8760")
                if not 1 <= len(args.name) <= 128:
                    parser.error("--name must contain between 1 and 128 characters")
                expires_at = (
                    None
                    if args.expires_hours == 0
                    else utc_now() + timedelta(hours=args.expires_hours)
                )
                issued = issue_agent_token(session, args.name, expires_at)
                print("Agent token created. It is shown only once:")
                print(issued.plaintext)
                print(f"Token ID: {issued.record.id}")
            elif args.command == "list":
                records = session.scalars(
                    select(AgentToken).order_by(AgentToken.created_at.desc())
                ).all()
                if not records:
                    print("No agent tokens found.")
                for record in records:
                    if record.revoked_at:
                        state = "revoked"
                    elif agent_token_is_expired(record):
                        state = "expired"
                    else:
                        state = "active"
                    binding = record.node_id or "unassigned"
                    expiry = record.expires_at.isoformat() if record.expires_at else "never"
                    print(f"{record.id}  {state:7}  {binding}  {expiry}  {record.name}")
            elif args.command == "revoke":
                if not revoke_agent_token(session, args.token_id):
                    parser.exit(1, f"Token not found: {args.token_id}\n")
                print(f"Token revoked: {args.token_id}")
    except SQLAlchemyError as exc:
        parser.exit(2, f"Database operation failed: {exc}\n")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
