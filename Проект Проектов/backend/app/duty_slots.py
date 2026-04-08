from __future__ import annotations

from datetime import date, datetime, time

SLOT_START_HOUR = 7
SLOT_COUNT = 11
SLOT_MAX_INDEX = SLOT_COUNT - 1


def slot_start_time_str(slot: int) -> str:
    return (time(hour=SLOT_START_HOUR + slot, minute=0)).strftime("%H:%M")


def duty_slot_for_dt(dt: datetime) -> tuple[date, int] | tuple[None, None]:
    slot = dt.hour - SLOT_START_HOUR
    if slot < 0 or slot > SLOT_MAX_INDEX:
        return None, None
    return dt.date(), slot
