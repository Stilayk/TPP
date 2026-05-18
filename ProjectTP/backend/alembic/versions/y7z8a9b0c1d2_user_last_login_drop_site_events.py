"""users.last_login_at; drop site_login_events after backfill

Revision ID: y7z8a9b0c1d2
Revises: x1y2z3a4b5c6
Create Date: 2026-05-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "y7z8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "x1y2z3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_last_login_at", "users", ["last_login_at"], unique=False)
    bind = op.get_bind()
    insp = inspect(bind)
    if "site_login_events" in insp.get_table_names():
        op.execute(
            """
            UPDATE users AS u
            SET last_login_at = sub.mx
            FROM (
                SELECT user_id, MAX(created_at) AS mx
                FROM site_login_events
                GROUP BY user_id
            ) AS sub
            WHERE u.id = sub.user_id
            """
        )
        op.drop_table("site_login_events")


def downgrade() -> None:
    op.drop_index("ix_users_last_login_at", table_name="users", if_exists=True)
    op.drop_column("users", "last_login_at")
