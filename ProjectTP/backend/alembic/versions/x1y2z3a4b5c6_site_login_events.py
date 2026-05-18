"""site_login_events for analytics (who logged in when)

Revision ID: x1y2z3a4b5c6
Revises: v7w8x9y0z1a2
Create Date: 2026-05-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "x1y2z3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "v7w8x9y0z1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_login_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_site_login_events_user_id", "site_login_events", ["user_id"], unique=False)
    op.create_index("ix_site_login_events_created_at", "site_login_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_site_login_events_created_at", table_name="site_login_events")
    op.drop_index("ix_site_login_events_user_id", table_name="site_login_events")
    op.drop_table("site_login_events")
