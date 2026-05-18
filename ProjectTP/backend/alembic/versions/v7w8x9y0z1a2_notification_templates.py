"""notification templates in duty_notification_settings

Revision ID: v7w8x9y0z1a2
Revises: p1q2r3s4t5u6
Create Date: 2026-05-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "v7w8x9y0z1a2"
down_revision: Union[str, Sequence[str], None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "duty_notification_settings",
        sa.Column(
            "upcoming_5m_template",
            sa.Text(),
            nullable=False,
            server_default=sa.text(
                "'Через 5 минут начинается ваше дежурство: {start_time}, дата {date}.'"
            ),
        ),
    )
    op.add_column(
        "duty_notification_settings",
        sa.Column(
            "start_personal_template",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'Ваше дежурство началось: {start_time}, дата {date}.'"),
        ),
    )
    op.add_column(
        "duty_notification_settings",
        sa.Column(
            "start_chat_template",
            sa.Text(),
            nullable=False,
            server_default=sa.text(
                "'На следующий час дежурным заступает {employee}, слот {start_time}, дата {date}.'"
            ),
        ),
    )
    op.add_column(
        "duty_notification_settings",
        sa.Column(
            "test_with_slot_template",
            sa.Text(),
            nullable=False,
            server_default=sa.text(
                "'Уведомление: сегодня ваше дежурство в {start_time}. Хорошего вам дня. Обнял, приподнял, покружил, поставил.'"
            ),
        ),
    )
    op.add_column(
        "duty_notification_settings",
        sa.Column(
            "test_without_slot_template",
            sa.Text(),
            nullable=False,
            server_default=sa.text(
                "'Уведомление: на сегодня у вас нет слота в графике дежурств. Хорошего вам дня. Обнял, приподнял, покружил, поставил.'"
            ),
        ),
    )
    op.alter_column("duty_notification_settings", "upcoming_5m_template", server_default=None)
    op.alter_column("duty_notification_settings", "start_personal_template", server_default=None)
    op.alter_column("duty_notification_settings", "start_chat_template", server_default=None)
    op.alter_column("duty_notification_settings", "test_with_slot_template", server_default=None)
    op.alter_column("duty_notification_settings", "test_without_slot_template", server_default=None)


def downgrade() -> None:
    op.drop_column("duty_notification_settings", "test_without_slot_template")
    op.drop_column("duty_notification_settings", "test_with_slot_template")
    op.drop_column("duty_notification_settings", "start_chat_template")
    op.drop_column("duty_notification_settings", "start_personal_template")
    op.drop_column("duty_notification_settings", "upcoming_5m_template")
