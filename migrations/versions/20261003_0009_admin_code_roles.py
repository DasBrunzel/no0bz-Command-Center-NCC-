"""Add the simple Commander and Beta-Tester dashboard roles."""

import sqlalchemy as sa
from alembic import op

revision = "20261003_0009"
down_revision = "20261003_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_codes") as batch:
        batch.add_column(
            sa.Column(
                "access_role",
                sa.String(32),
                nullable=False,
                server_default="commander",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("admin_codes") as batch:
        batch.drop_column("access_role")
