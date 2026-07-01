"""Генерация графика дежурств: пул без bootstrap-админа, фикс 09:00 → user, раздельные лимиты утро/день.

Многодневная генерация в одной транзакции: после каждого дня вызывается flush сессии, чтобы запросы
«кто дежурил вчера» видели назначения предыдущего дня (см. database.Session autoflush=False).

Нерабочие дни: суббота/воскресенье и официальные праздники РФ (`duty_rf_holidays`, пакет `holidays`).

Утренние (07:00–08:00) и обычные (09:00–17:00) слоты генерируются одной кнопкой, но с независимыми
счётчиками: макс. 2 утренних и макс. 2 обычных на человека в день.
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.deps import is_bootstrap_admin_account
from app.duty_leave_ops import user_ids_on_leave_for_day
from app.duty_rf_holidays import is_non_working_for_duty_generation
from app.duty_slots import (
    MORNING_SLOT_INDEXES,
    REGULAR_SLOT_COUNT,
    SLOT_09_00_INDEX,
    SLOT_COUNT,
)
from app.models import DutyAssignment, User

MAX_MORNING_DUTIES_PER_DAY = 2
MAX_REGULAR_DUTIES_PER_DAY = 2
USERNAME_09 = "user"
MORNING_FIRST_SLOT_INDEX = MORNING_SLOT_INDEXES[0]
MORNING_SECOND_SLOT_INDEX = MORNING_SLOT_INDEXES[1]
MORNING_SLOT_SET = set(MORNING_SLOT_INDEXES)


def _is_morning_slot(slot: int) -> bool:
    return slot in MORNING_SLOT_SET


def generation_pool_users(db) -> list[User]:
    rows = db.execute(
        select(User)
        .where(User.role.in_(("support", "admin")), User.is_active_for_duties == True)  # noqa: E712
        .order_by(User.id)
    ).scalars().all()
    return [u for u in rows if not is_bootstrap_admin_account(u)]


def morning_generation_pool_users(db) -> list[User]:
    rows = db.execute(
        select(User)
        .where(
            User.role.in_(("support", "admin")),
            User.is_active_for_duties == True,  # noqa: E712
            User.is_eligible_for_morning_duties == True,  # noqa: E712
        )
        .order_by(User.id)
    ).scalars().all()
    return [u for u in rows if not is_bootstrap_admin_account(u)]


def resolve_nine_am_user(db, pool_ids: set[int]) -> User:
    u = db.execute(
        select(User).where(
            func.lower(User.username) == USERNAME_09,
            User.is_active_for_duties == True,  # noqa: E712
            User.role.in_(("support", "admin")),
        )
    ).scalar_one_or_none()
    if not u or u.id not in pool_ids:
        raise HTTPException(
            status_code=400,
            detail='Для генерации нужен активный к дежурствам сотрудник с логином "user" (слот 09:00).',
        )
    return u


def _yesterday_counts(
    tx_db,
    d: date,
    pool_ids: list[int],
    *,
    morning: bool,
) -> dict[int, int]:
    if not pool_ids:
        return {}
    stmt = (
        select(DutyAssignment.support_user_id, func.count())
        .where(DutyAssignment.date == d, DutyAssignment.support_user_id.in_(pool_ids))
        .group_by(DutyAssignment.support_user_id)
    )
    if morning:
        stmt = stmt.where(DutyAssignment.slot.in_(MORNING_SLOT_INDEXES))
    else:
        stmt = stmt.where(~DutyAssignment.slot.in_(MORNING_SLOT_INDEXES))
    rows = tx_db.execute(stmt).all()
    return {int(uid): int(c) for uid, c in rows}


def _yesterday_slots_by_user(tx_db, d: date, pool_ids: list[int]) -> dict[int, set[int]]:
    if not pool_ids:
        return {}
    rows = tx_db.execute(
        select(DutyAssignment.support_user_id, DutyAssignment.slot).where(
            DutyAssignment.date == d,
            DutyAssignment.support_user_id.in_(pool_ids),
        )
    ).all()
    acc: dict[int, set[int]] = defaultdict(set)
    for uid, slot in rows:
        acc[int(uid)].add(int(slot))
    return dict(acc)


def _had_same_morning_block_yesterday(y_slots: set[int]) -> bool:
    return bool(y_slots & MORNING_SLOT_SET)


def _had_same_regular_slot_yesterday(y_slots: set[int], current_slot: int) -> bool:
    regular_y = {s for s in y_slots if s not in MORNING_SLOT_SET}
    return current_slot in regular_y


def _any_pool_without_slot_today(day_counts: dict[int, int], pool_ids: list[int]) -> bool:
    return any(day_counts.get(uid, 0) == 0 for uid in pool_ids)


def _eligible_for_next_slot(
    day_counts: dict[int, int],
    pool_ids: list[int],
    max_per_day: int,
) -> list[int]:
    out: list[int] = []
    for uid in pool_ids:
        n = day_counts.get(uid, 0)
        if n >= max_per_day:
            continue
        if n >= 1 and _any_pool_without_slot_today(day_counts, pool_ids):
            continue
        out.append(uid)
    return out


def _pick_user_for_slot(
    pool_ids: list[int],
    day_counts: dict[int, int],
    global_counts: dict[int, int],
    yesterday_counts: dict[int, int],
    yesterday_slots_by_user: dict[int, set[int]],
    pool_gt_slots: bool,
    current_slot: int,
    max_per_day: int,
    morning: bool,
    rng: random.Random,
) -> int:
    eligible = _eligible_for_next_slot(day_counts, pool_ids, max_per_day)
    if not eligible:
        kind = "утренний" if morning else "обычный"
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось назначить {kind} слот: нет сотрудника, удовлетворяющего лимитам "
            f"(макс. {max_per_day}/день и равномерность внутри дня).",
        )

    if pool_gt_slots:
        must = [uid for uid in pool_ids if yesterday_counts.get(uid, 0) == 0 and day_counts.get(uid, 0) == 0]
        narrowed = [uid for uid in eligible if uid in must]
        if narrowed:
            eligible = narrowed

    if morning:
        prefer_no_repeat = [
            uid
            for uid in eligible
            if not _had_same_morning_block_yesterday(yesterday_slots_by_user.get(uid, set()))
        ]
    else:
        prefer_no_repeat = [
            uid
            for uid in eligible
            if not _had_same_regular_slot_yesterday(yesterday_slots_by_user.get(uid, set()), current_slot)
        ]
    if prefer_no_repeat:
        eligible = prefer_no_repeat

    min_g = min(global_counts[uid] for uid in eligible)
    candidates = [uid for uid in eligible if global_counts[uid] == min_g]
    return int(rng.choice(candidates))


def _global_counts_before(
    tx_db,
    *,
    start_date: date,
    user_ids: list[int],
    morning: bool,
) -> dict[int, int]:
    counts = {uid: 0 for uid in user_ids}
    if not user_ids:
        return counts
    stmt = (
        select(DutyAssignment.support_user_id, func.count())
        .where(DutyAssignment.support_user_id.in_(user_ids), DutyAssignment.date < start_date)
        .group_by(DutyAssignment.support_user_id)
    )
    if morning:
        stmt = stmt.where(DutyAssignment.slot.in_(MORNING_SLOT_INDEXES))
    else:
        stmt = stmt.where(~DutyAssignment.slot.in_(MORNING_SLOT_INDEXES))
    for uid, c in tx_db.execute(stmt).all():
        counts[int(uid)] = int(c)
    return counts


def run_generation(
    tx_db,
    *,
    start_date: date,
    end_date: date,
    overwrite: bool,
    existing_in_range: dict[tuple[date, int], int],
    rng: random.SystemRandom,
) -> int:
    base_users = generation_pool_users(tx_db)
    base_ids = [u.id for u in base_users]
    morning_base_users = morning_generation_pool_users(tx_db)
    morning_base_ids = [u.id for u in morning_base_users]

    if not base_ids:
        raise HTTPException(
            status_code=400,
            detail="Нет сотрудников для генерации (support/admin с активными дежурствами, кроме учётной записи bootstrap-админа).",
        )
    if not morning_base_ids:
        raise HTTPException(
            status_code=400,
            detail="Нет сотрудников с доступом к утренним дежурствам (07:00–08:00).",
        )

    min_morning_pool = 1
    min_regular_pool = (REGULAR_SLOT_COUNT + MAX_REGULAR_DUTIES_PER_DAY - 1) // MAX_REGULAR_DUTIES_PER_DAY

    def _regular_pool_ids_for_day(d: date) -> list[int]:
        off = user_ids_on_leave_for_day(tx_db, day=d)
        return [i for i in base_ids if i not in off]

    def _morning_pool_ids_for_day(d: date) -> list[int]:
        off = user_ids_on_leave_for_day(tx_db, day=d)
        return [i for i in morning_base_ids if i not in off]

    for day_index in range((end_date - start_date).days + 1):
        current_day = start_date + timedelta(days=day_index)
        if is_non_working_for_duty_generation(current_day):
            continue
        morning_pool_ids = _morning_pool_ids_for_day(current_day)
        regular_pool_ids = _regular_pool_ids_for_day(current_day)
        if len(morning_pool_ids) < min_morning_pool:
            raise HTTPException(
                status_code=400,
                detail=f"На {current_day.isoformat()} в пуле утренних дежурств слишком мало сотрудников "
                f"(нужно не меньше {min_morning_pool}): часть отмечена отсутствием в генерации на этот день.",
            )
        if len(regular_pool_ids) < min_regular_pool:
            raise HTTPException(
                status_code=400,
                detail=f"На {current_day.isoformat()} в пуле обычных дежурств слишком мало сотрудников "
                f"(нужно не меньше {min_regular_pool}): часть отмечена отсутствием в генерации на этот день.",
            )
        resolve_nine_am_user(tx_db, set(regular_pool_ids))

    if overwrite:
        tx_db.execute(
            delete(DutyAssignment).where(
                DutyAssignment.date >= start_date,
                DutyAssignment.date <= end_date,
            )
        )
        tx_db.commit()

    global_morning_counts = _global_counts_before(
        tx_db, start_date=start_date, user_ids=morning_base_ids, morning=True
    )
    global_regular_counts = _global_counts_before(
        tx_db, start_date=start_date, user_ids=base_ids, morning=False
    )

    created = 0

    for day_index in range((end_date - start_date).days + 1):
        current_day = start_date + timedelta(days=day_index)
        yesterday = current_day - timedelta(days=1)
        morning_pool_ids = _morning_pool_ids_for_day(current_day)
        regular_pool_ids = _regular_pool_ids_for_day(current_day)
        morning_pool_ids_set = set(morning_pool_ids)
        regular_pool_ids_set = set(regular_pool_ids)
        nine_user = resolve_nine_am_user(tx_db, regular_pool_ids_set)
        pool_gt_morning = len(morning_pool_ids) > len(MORNING_SLOT_INDEXES)
        pool_gt_regular = len(regular_pool_ids) > REGULAR_SLOT_COUNT

        yesterday_morning_counts = _yesterday_counts(
            tx_db, yesterday, morning_pool_ids, morning=True
        )
        yesterday_regular_counts = _yesterday_counts(
            tx_db, yesterday, regular_pool_ids, morning=False
        )
        yesterday_slots_by_user = _yesterday_slots_by_user(tx_db, yesterday, regular_pool_ids)
        morning_day_counts: dict[int, int] = defaultdict(int)
        regular_day_counts: dict[int, int] = defaultdict(int)

        morning_pair_user_id: int | None = None
        skip_new_assignments = is_non_working_for_duty_generation(current_day)

        tail = [
            s
            for s in range(SLOT_COUNT)
            if s != SLOT_09_00_INDEX and s not in MORNING_SLOT_SET
        ]
        rng.shuffle(tail)
        slot_order = [SLOT_09_00_INDEX, MORNING_FIRST_SLOT_INDEX, MORNING_SECOND_SLOT_INDEX] + tail

        for slot in slot_order:
            key = (current_day, slot)
            is_morning = _is_morning_slot(slot)

            if (not overwrite) and key in existing_in_range:
                uid = existing_in_range[key]
                valid_pool = morning_pool_ids_set if is_morning else regular_pool_ids_set
                if uid in valid_pool:
                    if is_morning:
                        morning_day_counts[uid] = morning_day_counts.get(uid, 0) + 1
                        global_morning_counts[uid] = global_morning_counts.get(uid, 0) + 1
                        if slot == MORNING_FIRST_SLOT_INDEX:
                            morning_pair_user_id = uid
                    else:
                        regular_day_counts[uid] = regular_day_counts.get(uid, 0) + 1
                        global_regular_counts[uid] = global_regular_counts.get(uid, 0) + 1
                continue

            if skip_new_assignments:
                continue

            if slot == SLOT_09_00_INDEX:
                uid = nine_user.id
            elif slot == MORNING_SECOND_SLOT_INDEX and morning_pair_user_id is not None:
                uid = morning_pair_user_id
            elif is_morning:
                uid = _pick_user_for_slot(
                    morning_pool_ids,
                    morning_day_counts,
                    global_morning_counts,
                    yesterday_morning_counts,
                    yesterday_slots_by_user,
                    pool_gt_morning,
                    slot,
                    MAX_MORNING_DUTIES_PER_DAY,
                    morning=True,
                    rng=rng,
                )
                if slot == MORNING_FIRST_SLOT_INDEX:
                    morning_pair_user_id = uid
            else:
                uid = _pick_user_for_slot(
                    regular_pool_ids,
                    regular_day_counts,
                    global_regular_counts,
                    yesterday_regular_counts,
                    yesterday_slots_by_user,
                    pool_gt_regular,
                    slot,
                    MAX_REGULAR_DUTIES_PER_DAY,
                    morning=False,
                    rng=rng,
                )

            tx_db.add(DutyAssignment(date=current_day, slot=slot, support_user_id=uid))
            if is_morning:
                morning_day_counts[uid] = morning_day_counts.get(uid, 0) + 1
                global_morning_counts[uid] = global_morning_counts.get(uid, 0) + 1
            else:
                regular_day_counts[uid] = regular_day_counts.get(uid, 0) + 1
                global_regular_counts[uid] = global_regular_counts.get(uid, 0) + 1
            created += 1

        tx_db.flush()

    tx_db.commit()
    return created
