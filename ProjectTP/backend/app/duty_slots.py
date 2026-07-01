from __future__ import annotations

from datetime import date, datetime, time

SLOT_START_HOUR = 7
SLOT_COUNT = 11
SLOT_MAX_INDEX = SLOT_COUNT - 1
# Слот часа 09:00 (индекс = час − SLOT_START_HOUR).
SLOT_09_00_INDEX = 9 - SLOT_START_HOUR
MORNING_SLOT_INDEXES = (7 - SLOT_START_HOUR, 8 - SLOT_START_HOUR)
REGULAR_SLOT_COUNT = SLOT_COUNT - len(MORNING_SLOT_INDEXES)


def slot_start_time_str(slot: int) -> str:
    return (time(hour=SLOT_START_HOUR + slot, minute=0)).strftime("%H:%M")


def duty_slot_for_dt(dt: datetime) -> tuple[date, int] | tuple[None, None]:
    slot = dt.hour - SLOT_START_HOUR
    if slot < 0 or slot > SLOT_MAX_INDEX:
        return None, None
    return dt.date(), slot
