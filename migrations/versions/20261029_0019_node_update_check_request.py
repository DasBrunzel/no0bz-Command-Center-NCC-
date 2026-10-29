"""Let commanders ask a node to check for updates immediately."""

import sqlalchemy as sa
from alembic import op

revision = "20261029_0019"
down_revision = "20261026_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("update_check_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("update_check_requested_at")
