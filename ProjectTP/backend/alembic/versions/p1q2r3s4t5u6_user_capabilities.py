"""user capabilities for delegated admin operations

Revision ID: p1q2r3s4t5u6
Revises: n5o6p7q8r9t0
Create Date: 2026-05-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, Sequence[str], None] = "n5o6p7q8r9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("can_manage_duties", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("can_manage_reports", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("can_manage_notifications", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("users", "can_manage_duties", server_default=None)
    op.alter_column("users", "can_manage_reports", server_default=None)
    op.alter_column("users", "can_manage_notifications", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "can_manage_notifications")
    op.drop_column("users", "can_manage_reports")
    op.drop_column("users", "can_manage_duties")
