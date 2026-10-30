"""Let nodes follow the newest release and keep pinned releases from downgrading."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_0025"
down_revision = "20261030_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.add_column(sa.Column("release_allow_downgrade", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Every node starts out following the newest release; old pins such as a
    # forgotten beta would otherwise pull freshly installed agents back.
    op.execute(sa.text("UPDATE nodes SET pending_release_id = NULL"))


def downgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("release_allow_downgrade")
