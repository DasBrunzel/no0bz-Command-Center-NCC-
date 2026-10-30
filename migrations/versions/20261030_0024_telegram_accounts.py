"""Temperature thresholds, per-account Telegram chats and the weekly recap."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_0024"
down_revision = "20261030_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alert_policy") as batch:
        batch.add_column(sa.Column("cpu_temperature_threshold", sa.Integer(), nullable=False, server_default="90"))
        batch.add_column(sa.Column("gpu_temperature_threshold", sa.Integer(), nullable=False, server_default="85"))
        batch.add_column(sa.Column("drive_temperature_threshold", sa.Integer(), nullable=False, server_default="65"))
    op.create_table(
        "telegram_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("chat_id", sa.String(32), nullable=False),
        sa.Column("telegram_name", sa.String(128), nullable=True),
        sa.Column("weekly_recap", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "telegram_link_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "telegram_bot_state",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("update_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_recap_week", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("telegram_bot_state")
    op.drop_table("telegram_link_codes")
    op.drop_table("telegram_links")
    with op.batch_alter_table("alert_policy") as batch:
        batch.drop_column("drive_temperature_threshold")
        batch.drop_column("gpu_temperature_threshold")
        batch.drop_column("cpu_temperature_threshold")
