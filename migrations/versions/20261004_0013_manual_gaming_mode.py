"""Add the temporary, dashboard-controlled gaming mode marker."""

import sqlalchemy as sa
from alembic import op

revision = "20261004_0013"
down_revision = "20261003_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("gaming_mode_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("gaming_mode_until")
