"""Нерабочие дни РФ для автогенерации графика дежурств.

Полные нерабочие дни по производственному календарю (пакет `holidays`, страна RU) обрабатываются
как выходные: слоты не создаются. **Суббота и воскресенье** — по-прежнему `weekday() >= 5`.

Предпраздничные **сокращённые** рабочие дни в календаре остаются рабочими для почасовых слотов 07:00–17:00.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache


@lru_cache(maxsize=48)
def _ru_holidays(year: int):
    import holidays

    return holidays.Russia(years=[year])


def is_rf_public_holiday(d: date) -> bool:
    """True, если дата — официальный нерабочий праздничный/переносимый день в РФ (не суббота/воскресенье сами по себе)."""
    return d in _ru_holidays(d.year)


def is_non_working_for_duty_generation(d: date) -> bool:
    """День, в который автогенерация не создаёт назначения (выходные + праздники РФ)."""
    return d.weekday() >= 5 or is_rf_public_holiday(d)
