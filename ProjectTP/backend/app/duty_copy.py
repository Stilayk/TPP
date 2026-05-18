"""Копирование графика дежурств с одного диапазона дат на другой (шаблон по дням)."""

from __future__ import annotations

from app.duty_slots import SLOT_COUNT


def slot_updates_for_copy(
    src_by_slot: dict[int, int],
    tgt_by_slot: dict[int, int],
    *,
    overwrite: bool,
) -> list[tuple[int, int | None]]:
    """Полный набор слотов 0..SLOT_COUNT-1 для целевого дня после слияния с шаблоном источника."""
    out: list[tuple[int, int | None]] = []
    for slot in range(SLOT_COUNT):
        sv = src_by_slot.get(slot)
        tv = tgt_by_slot.get(slot)
        if overwrite:
            final = sv
        else:
            final = tv if tv is not None else sv
        out.append((slot, final))
    return out
