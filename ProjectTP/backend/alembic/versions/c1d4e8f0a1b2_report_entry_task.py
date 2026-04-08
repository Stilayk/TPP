"""report_entry_task

Revision ID: c1d4e8f0a1b2
Revises: b7e2c0d14f2a
Create Date: 2026-04-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d4e8f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b7e2c0d14f2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "report_entries",
        sa.Column(
            "task",
            sa.String(length=500),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )


def downgrade() -> None:
    op.drop_column("report_entries", "task")
