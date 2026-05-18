"""employee_exit_instruction_shares for public QR links

Revision ID: n5o6p7q8r9t0
Revises: g8h9i0j1k2l3
Create Date: 2026-04-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "n5o6p7q8r9t0"
down_revision: Union[str, Sequence[str], None] = "g8h9i0j1k2l3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_exit_instruction_shares",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("public_view_url", sa.String(length=768), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_employee_exit_instruction_shares_token"),
    )
    op.create_index(
        "ix_employee_exit_instruction_shares_token",
        "employee_exit_instruction_shares",
        ["token"],
        unique=False,
    )
    op.create_index(
        "ix_employee_exit_instruction_shares_expires_at",
        "employee_exit_instruction_shares",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_employee_exit_instruction_shares_expires_at", table_name="employee_exit_instruction_shares")
    op.drop_index("ix_employee_exit_instruction_shares_token", table_name="employee_exit_instruction_shares")
    op.drop_table("employee_exit_instruction_shares")
