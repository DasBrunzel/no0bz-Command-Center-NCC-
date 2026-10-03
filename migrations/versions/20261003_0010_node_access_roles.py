"""Persist the dashboard role on pairings, agent credentials, and nodes."""

import sqlalchemy as sa
from alembic import op

revision = "20261003_0010"
down_revision = "20261003_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("nodes", "agent_tokens", "agent_pairings"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(
                    "access_role",
                    sa.String(32),
                    nullable=False,
                    server_default="commander",
                )
            )


def downgrade() -> None:
    for table in ("agent_pairings", "agent_tokens", "nodes"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("access_role")
