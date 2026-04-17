"""duty_notification_settings: scheduler_enabled

Revision ID: g8h9i0j1k2l3
Revises: f1a2b3c4d5e6
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL: идемпотентно, без inspect (надёжнее в разных состояниях БД)
    op.execute(
        sa.text(
            """
            ALTER TABLE duty_notification_settings
            ADD COLUMN IF NOT EXISTS scheduler_enabled BOOLEAN NOT NULL DEFAULT TRUE
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE duty_notification_settings
            DROP COLUMN IF EXISTS scheduler_enabled
            """
        )
    )
