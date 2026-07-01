"""user morning duty eligibility flag

Revision ID: a1b2c3d4e5f6
Revises: z5a6b7c8d9e0
Create Date: 2026-06-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "z5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_eligible_for_morning_duties", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.execute(
        "UPDATE users SET is_eligible_for_morning_duties = is_active_for_duties"
    )
    op.alter_column("users", "is_eligible_for_morning_duties", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_eligible_for_morning_duties")
