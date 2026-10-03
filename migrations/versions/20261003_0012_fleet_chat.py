"""Add durable Fleet chat messages and attachment metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20261003_0012"
down_revision = "20261003_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fleet_chat_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("sender_node_id", sa.String(length=36), nullable=True),
        sa.Column("sender_name", sa.String(length=128), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_format", sa.String(length=16), nullable=False, server_default="plain"),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_path", sa.String(length=255), nullable=True),
        sa.Column("attachment_type", sa.String(length=128), nullable=True),
        sa.Column("attachment_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sender_node_id"], ["nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fleet_chat_messages_created", "fleet_chat_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_fleet_chat_messages_created", table_name="fleet_chat_messages")
    op.drop_table("fleet_chat_messages")
