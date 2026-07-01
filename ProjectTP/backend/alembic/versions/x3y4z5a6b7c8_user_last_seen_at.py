"""rename users.last_login_at to last_seen_at

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x3y4z5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "w2x3y4z5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "last_login_at",
        new_column_name="last_seen_at",
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
    op.drop_index("ix_users_last_login_at", table_name="users")
    op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_last_seen_at", table_name="users")
    op.create_index("ix_users_last_login_at", "users", ["last_login_at"], unique=False)
    op.alter_column(
        "users",
        "last_seen_at",
        new_column_name="last_login_at",
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
