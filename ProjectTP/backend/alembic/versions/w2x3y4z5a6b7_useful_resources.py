"""useful resources catalog

Revision ID: w2x3y4z5a6b7
Revises: z1a2b3c4d5e6
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.useful_resources_seed import DEFAULT_USEFUL_RESOURCES

revision: str = "w2x3y4z5a6b7"
down_revision: Union[str, Sequence[str], None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "useful_resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("image_path", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("color", sa.String(length=32), nullable=False, server_default="#2563eb"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_useful_resources_slug"),
    )
    op.create_index("ix_useful_resources_slug", "useful_resources", ["slug"], unique=True)

    resources_table = sa.table(
        "useful_resources",
        sa.column("slug", sa.String()),
        sa.column("title", sa.String()),
        sa.column("description", sa.String()),
        sa.column("url", sa.String()),
        sa.column("image_path", sa.String()),
        sa.column("color", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("categories", sa.JSON()),
    )
    op.bulk_insert(
        resources_table,
        [
            {
                "slug": item["slug"],
                "title": item["title"],
                "description": item["description"],
                "url": item["url"],
                "image_path": item["image_path"],
                "color": item["color"],
                "sort_order": item["sort_order"],
                "categories": item["categories"],
            }
            for item in DEFAULT_USEFUL_RESOURCES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_useful_resources_slug", table_name="useful_resources")
    op.drop_table("useful_resources")
