from __future__ import annotations

from app.duty_copy import slot_updates_for_copy


def test_copy_fills_empty_targets_from_source() -> None:
    src = {0: 10, 1: 20}
    tgt: dict[int, int] = {}
    u = slot_updates_for_copy(src, tgt, overwrite=False)
    assert u[0] == (0, 10)
    assert u[1] == (1, 20)
    assert all(x[1] is None for x in u[2:])


def test_copy_respects_existing_when_not_overwrite() -> None:
    src = {0: 99, 1: 20}
    tgt = {0: 10}
    u = slot_updates_for_copy(src, tgt, overwrite=False)
    assert u[0] == (0, 10)
    assert u[1] == (1, 20)


def test_copy_overwrite_replaces_from_source() -> None:
    src = {0: 5}
    tgt = {0: 10, 1: 7}
    u = slot_updates_for_copy(src, tgt, overwrite=True)
    assert u[0] == (0, 5)
    assert u[1] == (1, None)
