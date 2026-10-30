"""Let users name unlabeled sensors such as mainboard fans."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_0021"
down_revision = "20261030_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("sensor_labels", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("sensor_labels")
