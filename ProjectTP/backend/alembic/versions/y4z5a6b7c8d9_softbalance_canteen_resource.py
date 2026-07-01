"""add useful resource: Менеджер лицензий для Столовых

Revision ID: y4z5a6b7c8d9
Revises: x3y4z5a6b7c8
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y4z5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "x3y4z5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROW = {
    "slug": "softbalance-canteen-licenses",
    "title": "Менеджер лицензий для Столовых",
    "description": "СофтБаланс — управление лицензиями столовых",
    "url": "http://10.0.15.18:5171/index",
    "image_path": "./resource-images/softbalance-license-manager.png",
    "color": "#1e40af",
    "sort_order": 110,
    "categories": ["services"],
}


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM useful_resources WHERE slug = :slug"),
        {"slug": _ROW["slug"]},
    ).first()
    if exists:
        return
    conn.execute(
        sa.text(
            """
            INSERT INTO useful_resources
                (slug, title, description, url, image_path, color, sort_order, categories)
            VALUES
                (:slug, :title, :description, :url, :image_path, :color, :sort_order, CAST(:categories AS JSON))
            """
        ),
        {**_ROW, "categories": '["services"]'},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM useful_resources WHERE slug = :slug"),
        {"slug": _ROW["slug"]},
    )
