"""admin_role_audit

Revision ID: b7e2c0d14f2a
Revises: a9ed29c6b953
Create Date: 2026-04-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e2c0d14f2a"
down_revision: Union[str, Sequence[str], None] = "a9ed29c6b953"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_role_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("action IN ('grant','revoke')", name="ck_admin_role_audit_action"),
    )
    op.create_index(op.f("ix_admin_role_audit_created_at"), "admin_role_audit", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_role_audit_created_at"), table_name="admin_role_audit")
    op.drop_table("admin_role_audit")
