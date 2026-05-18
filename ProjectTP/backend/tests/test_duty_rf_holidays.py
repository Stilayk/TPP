from __future__ import annotations

from datetime import date

import pytest

from app.duty_rf_holidays import is_non_working_for_duty_generation, is_rf_public_holiday


def test_may_first_is_rf_holiday() -> None:
    assert is_rf_public_holiday(date(2025, 5, 1))


def test_regular_tuesday_not_rf_holiday() -> None:
    assert not is_rf_public_holiday(date(2025, 5, 13))


def test_saturday_non_working_for_generation() -> None:
    # 2025-05-10 is Saturday
    assert is_non_working_for_duty_generation(date(2025, 5, 10))


def test_may_first_non_working_for_generation() -> None:
    assert is_non_working_for_duty_generation(date(2025, 5, 1))
