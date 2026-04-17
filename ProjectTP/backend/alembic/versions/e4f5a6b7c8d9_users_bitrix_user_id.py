"""users bitrix_user_id

Revision ID: e4f5a6b7c8d9
Revises: c1d4e8f0a1b2
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "c1d4e8f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bitrix_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "bitrix_user_id")
