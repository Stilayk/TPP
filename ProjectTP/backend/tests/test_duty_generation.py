"""Happy-path: приоритет без повтора того же слота вчера (если возможно)."""

from __future__ import annotations

import random

from app.duty_generation import (
    MORNING_FIRST_SLOT_INDEX,
    MORNING_SECOND_SLOT_INDEX,
    MAX_MORNING_DUTIES_PER_DAY,
    MAX_REGULAR_DUTIES_PER_DAY,
    _eligible_for_next_slot,
    _had_same_morning_block_yesterday,
    _had_same_regular_slot_yesterday,
    _pick_user_for_slot,
)


def test_pick_prefers_user_who_did_not_have_this_slot_yesterday():
    rng = random.Random(0)
    pool_ids = [101, 202]
    day_counts = {101: 0, 202: 0}
    global_counts = {101: 0, 202: 0}
    yesterday_counts = {101: 0, 202: 0}
    yesterday_slots = {101: {5}, 202: set()}
    uid = _pick_user_for_slot(
        pool_ids,
        day_counts,
        global_counts,
        yesterday_counts,
        yesterday_slots,
        pool_gt_slots=False,
        current_slot=5,
        max_per_day=MAX_REGULAR_DUTIES_PER_DAY,
        morning=False,
        rng=rng,
    )
    assert uid == 202


def test_pick_morning_prefers_user_without_morning_block_yesterday():
    rng = random.Random(0)
    pool_ids = [1, 2]
    day_counts = {1: 0, 2: 0}
    global_counts = {1: 0, 2: 0}
    yesterday_counts = {1: 0, 2: 0}
    yesterday_slots = {1: {MORNING_FIRST_SLOT_INDEX}, 2: set()}
    uid = _pick_user_for_slot(
        pool_ids,
        day_counts,
        global_counts,
        yesterday_counts,
        yesterday_slots,
        pool_gt_slots=False,
        current_slot=MORNING_FIRST_SLOT_INDEX,
        max_per_day=MAX_MORNING_DUTIES_PER_DAY,
        morning=True,
        rng=rng,
    )
    assert uid == 2


def test_morning_assignee_can_take_regular_slot_same_day():
    """Утренний дежурный с двумя утренними слотами допустим для обычного слота."""
    eligible = _eligible_for_next_slot(
        {12: MAX_MORNING_DUTIES_PER_DAY},
        [12, 34],
        MAX_REGULAR_DUTIES_PER_DAY,
    )
    assert 12 in eligible


def test_had_same_morning_block_yesterday():
    assert _had_same_morning_block_yesterday({MORNING_SECOND_SLOT_INDEX}) is True
    assert _had_same_morning_block_yesterday(set()) is False
    assert _had_same_morning_block_yesterday({5}) is False


def test_had_same_regular_slot_yesterday():
    assert _had_same_regular_slot_yesterday({3}, 3) is True
    assert _had_same_regular_slot_yesterday({3}, 4) is False
    assert _had_same_regular_slot_yesterday({MORNING_SECOND_SLOT_INDEX}, 5) is False
