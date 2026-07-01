"""add useful resource: MobiControl

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROW = {
    "slug": "mobicontrol",
    "title": "MobiControl",
    "description": "SOTI MobiControl — управление Apple Mac",
    "url": (
        "https://mdm.corp.hpdd.ru/MobiControl/WebConsole/home/dashboard/devices"
        "?subGroups=false"
    ),
    "image_path": "./resource-images/mobicontrol.png",
    "color": "#374151",
    "sort_order": 120,
    "categories": ["admin"],
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
        {**_ROW, "categories": '["admin"]'},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM useful_resources WHERE slug = :slug"),
        {"slug": _ROW["slug"]},
    )
