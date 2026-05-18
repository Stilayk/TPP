"""duty_participation_leave: дни без участия в автогенерации графика

Revision ID: k2l3m4n5o6p7
Revises: y7z8a9b0c1d2
Create Date: 2026-05-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, Sequence[str], None] = "y7z8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "duty_participation_leave",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("leave_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "leave_date", name="uq_duty_leave_user_date"),
    )
    op.create_index("ix_duty_participation_leave_leave_date", "duty_participation_leave", ["leave_date"], unique=False)
    op.create_index("ix_duty_participation_leave_user_id", "duty_participation_leave", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_duty_participation_leave_user_id", table_name="duty_participation_leave")
    op.drop_index("ix_duty_participation_leave_leave_date", table_name="duty_participation_leave")
    op.drop_table("duty_participation_leave")
