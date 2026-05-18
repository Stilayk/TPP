"""daily_reports.updated_at for report change history

Revision ID: z1a2b3c4d5e6
Revises: k2l3m4n5o6p7
Create Date: 2026-05-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "k2l3m4n5o6p7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("daily_reports", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE daily_reports SET updated_at = COALESCE(finalized_at, NOW() AT TIME ZONE 'UTC')"
        )
    )
    op.alter_column("daily_reports", "updated_at", nullable=False)
    op.create_index("ix_daily_reports_updated_at", "daily_reports", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_daily_reports_updated_at", table_name="daily_reports")
    op.drop_column("daily_reports", "updated_at")
