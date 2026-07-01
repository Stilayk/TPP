"""add useful resource: База знаний IT (DokuWiki)

Revision ID: z5a6b7c8d9e0
Revises: y4z5a6b7c8d9
Create Date: 2026-05-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "y4z5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROW = {
    "slug": "dokuwiki-it-kb",
    "title": "База знаний IT (DokuWiki)",
    "description": "Realize — база знаний техподдержки",
    "url": (
        "http://dokuwiki.corp.hpdd.ru/doku.php/"
        "%D1%82%D0%B5%D1%85%D0%BF%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%BA%D0%B0/exchange/start?do=login"
    ),
    "image_path": "./resource-images/dokuwiki-kb.png",
    "color": "#2563eb",
    "sort_order": 115,
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
