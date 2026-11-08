"""Let the commander switch alert delivery to the NCC Android app on and off."""

import sqlalchemy as sa
from alembic import op

revision = "20261108_0027"
down_revision = "20261107_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alert_policy") as batch:
        batch.add_column(sa.Column("app_alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("alert_policy") as batch:
        batch.drop_column("app_alerts_enabled")
