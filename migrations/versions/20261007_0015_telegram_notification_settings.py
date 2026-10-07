"""Add dashboard-editable Telegram presentation preferences."""

import sqlalchemy as sa
from alembic import op


revision = "20261007_0015"
down_revision = "20261007_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_notification_settings",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("warning_title", sa.String(length=128), nullable=False, server_default="NCC WARNUNG"),
        sa.Column("critical_title", sa.String(length=128), nullable=False, server_default="NCC KRITISCHE WARNUNG"),
        sa.Column("resolved_title", sa.String(length=128), nullable=False, server_default="NCC ENTWARNUNG"),
        sa.Column("footer", sa.String(length=256), nullable=False, server_default="NCC {version}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("telegram_notification_settings")
