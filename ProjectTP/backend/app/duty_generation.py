"""Генерация графика дежурств: пул без bootstrap-админа, фикс 09:00 → user, лимиты и приоритеты по ТЗ."""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.deps import is_bootstrap_admin_account
from app.duty_slots import SLOT_09_00_INDEX, SLOT_COUNT
from app.models import DutyAssignment, User

MAX_DUTIES_PER_DAY = 2
USERNAME_09 = "user"


def generation_pool_users(db) -> list[User]:
    rows = db.execute(
        select(User)
        .where(User.role.in_(("support", "admin")), User.is_active_for_duties == True)  # noqa: E712
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


def _yesterday_counts(tx_db, d: date, pool_ids: list[int]) -> dict[int, int]:
    if not pool_ids:
        return {}
    rows = tx_db.execute(
        select(DutyAssignment.support_user_id, func.count())
        .where(DutyAssignment.date == d, DutyAssignment.support_user_id.in_(pool_ids))
        .group_by(DutyAssignment.support_user_id)
    ).all()
    return {int(uid): int(c) for uid, c in rows}


def _any_pool_without_slot_today(day_counts: dict[int, int], pool_ids: list[int]) -> bool:
    return any(day_counts.get(uid, 0) == 0 for uid in pool_ids)


def _eligible_for_next_slot(day_counts: dict[int, int], pool_ids: list[int]) -> list[int]:
    out: list[int] = []
    for uid in pool_ids:
        n = day_counts.get(uid, 0)
        if n >= MAX_DUTIES_PER_DAY:
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
    pool_gt_slots: bool,
    rng: random.SystemRandom,
) -> int:
    eligible = _eligible_for_next_slot(day_counts, pool_ids)
    if not eligible:
        raise HTTPException(
            status_code=400,
            detail="Не удалось назначить слот: нет сотрудника, удовлетворяющего лимитам (макс. 2/день и равномерность внутри дня).",
        )

    if pool_gt_slots:
        must = [uid for uid in pool_ids if yesterday_counts.get(uid, 0) == 0 and day_counts.get(uid, 0) == 0]
        narrowed = [uid for uid in eligible if uid in must]
        if narrowed:
            eligible = narrowed

    min_g = min(global_counts[uid] for uid in eligible)
    candidates = [uid for uid in eligible if global_counts[uid] == min_g]
    return int(rng.choice(candidates))


def run_generation(
    tx_db,
    *,
    start_date: date,
    end_date: date,
    overwrite: bool,
    existing_in_range: dict[tuple[date, int], int],
    rng: random.SystemRandom,
) -> int:
    pool_users = generation_pool_users(tx_db)
    pool_ids = [u.id for u in pool_users]
    pool_ids_set = set(pool_ids)
    if not pool_ids:
        raise HTTPException(
            status_code=400,
            detail="Нет сотрудников для генерации (support/admin с активными дежурствами, кроме учётной записи bootstrap-админа).",
        )

    nine_user = resolve_nine_am_user(tx_db, pool_ids_set)
    pool_gt_slots = len(pool_ids) > SLOT_COUNT

    min_pool = (SLOT_COUNT + MAX_DUTIES_PER_DAY - 1) // MAX_DUTIES_PER_DAY
    if len(pool_ids) < min_pool:
        raise HTTPException(
            status_code=400,
            detail=f"В пуле генерации слишком мало сотрудников: нужно не меньше {min_pool}, "
            f"чтобы закрыть {SLOT_COUNT} слотов при лимите {MAX_DUTIES_PER_DAY} дежурств в день на человека.",
        )

    if overwrite:
        tx_db.execute(
            delete(DutyAssignment).where(
                DutyAssignment.date >= start_date,
                DutyAssignment.date <= end_date,
            )
        )
        tx_db.commit()

    global_counts = {uid: 0 for uid in pool_ids}
    for uid in pool_ids:
        global_counts[uid] = int(
            tx_db.execute(
                select(func.count())
                .select_from(DutyAssignment)
                .where(DutyAssignment.support_user_id == uid, DutyAssignment.date < start_date)
            ).scalar_one()
        )

    created = 0
    slot_order = [SLOT_09_00_INDEX] + [s for s in range(SLOT_COUNT) if s != SLOT_09_00_INDEX]

    for day_index in range((end_date - start_date).days + 1):
        current_day = start_date + timedelta(days=day_index)
        yesterday = current_day - timedelta(days=1)
        yesterday_counts = _yesterday_counts(tx_db, yesterday, pool_ids)
        day_counts: dict[int, int] = defaultdict(int)

        for slot in slot_order:
            key = (current_day, slot)
            if (not overwrite) and key in existing_in_range:
                uid = existing_in_range[key]
                if uid in pool_ids_set:
                    day_counts[uid] = day_counts.get(uid, 0) + 1
                    global_counts[uid] = global_counts.get(uid, 0) + 1
                continue

            if slot == SLOT_09_00_INDEX:
                uid = nine_user.id
            else:
                uid = _pick_user_for_slot(
                    pool_ids,
                    day_counts,
                    global_counts,
                    yesterday_counts,
                    pool_gt_slots,
                    rng,
                )

            tx_db.add(DutyAssignment(date=current_day, slot=slot, support_user_id=uid))
            day_counts[uid] = day_counts.get(uid, 0) + 1
            global_counts[uid] = global_counts.get(uid, 0) + 1
            created += 1

    tx_db.commit()
    return created
