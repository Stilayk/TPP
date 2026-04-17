"""duty notification settings

Revision ID: f1a2b3c4d5e6
Revises: e4f5a6b7c8d9
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "duty_notification_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("selected_method", sa.String(length=8), nullable=False, server_default="cron"),
        sa.Column("cron_enabled_upcoming_5m", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cron_enabled_start", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cron_enabled_chat_on_start", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("n8n_enabled_upcoming_5m", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("n8n_enabled_start", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("n8n_enabled_chat_on_start", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("id = 1", name="ck_duty_notification_settings_singleton"),
        sa.CheckConstraint("selected_method IN ('cron','n8n')", name="ck_duty_notification_settings_method"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO duty_notification_settings (
            id,
            selected_method,
            cron_enabled_upcoming_5m,
            cron_enabled_start,
            cron_enabled_chat_on_start,
            n8n_enabled_upcoming_5m,
            n8n_enabled_start,
            n8n_enabled_chat_on_start
        ) VALUES (1, 'cron', true, true, true, true, true, true)
        """
    )


def downgrade() -> None:
    op.drop_table("duty_notification_settings")
