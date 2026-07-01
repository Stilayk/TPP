from __future__ import annotations

import pytest

from app.useful_resources_seed import normalize_resource_categories


def test_normalize_categories_accepts_multiple() -> None:
    assert normalize_resource_categories(["services", "admin"]) == ["services", "admin"]


def test_normalize_categories_dedupes() -> None:
    assert normalize_resource_categories(["services", "services"]) == ["services"]


def test_normalize_categories_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Неизвестная категория"):
        normalize_resource_categories(["nope"])


def test_normalize_categories_requires_at_least_one() -> None:
    with pytest.raises(ValueError):
        normalize_resource_categories([])
