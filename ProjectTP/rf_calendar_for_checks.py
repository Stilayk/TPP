"""Дни без автогенерации дежурств для smoke-скриптов в каталоге `ProjectTP/` (выходные + праздники РФ)."""

from __future__ import annotations

from datetime import date
from functools import lru_cache


@lru_cache(maxsize=48)
def _ru_holidays(year: int):
    import holidays

    return holidays.Russia(years=[year])


def is_day_skipped_by_auto_generation(d: date) -> bool:
    """Совпадает с логикой `app.duty_rf_holidays.is_non_working_for_duty_generation`."""
    if d.weekday() >= 5:
        return True
    try:
        return d in _ru_holidays(d.year)
    except Exception:
        return False
