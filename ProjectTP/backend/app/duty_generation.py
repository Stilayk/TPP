"""Генерация графика дежурств: пул без bootstrap-админа, фикс 09:00 → user, лимиты и приоритеты по ТЗ.

Многодневная генерация в одной транзакции: после каждого дня вызывается flush сессии, чтобы запросы
«кто дежурил вчера» (_yesterday_counts) видели назначения предыдущего дня (см. database.Session autoflush=False).

Нерабочие дни: суббота/воскресенье и официальные праздники РФ (`duty_rf_holidays`, пакет `holidays`).

Разнообразие по дням: порядок почасовых слотов (кроме 09:00 и пары 07–08) перемешивается каждый день;
при выборе сотрудника в приоритете те, кто вчера не дежурил в этом же слоте (для утра 07–08 — не в
обоих утренних слотах), если иначе возможно; дальше — минимум глобального счётчика и случайный выбор среди равных.
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
from app.duty_slots import SLOT_09_00_INDEX, SLOT_COUNT, SLOT_START_HOUR
from app.models import DutyAssignment, User

MAX_DUTIES_PER_DAY = 2
USERNAME_09 = "user"
MORNING_FIRST_SLOT_INDEX = 7 - SLOT_START_HOUR
MORNING_SECOND_SLOT_INDEX = 8 - SLOT_START_HOUR


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


def _yesterday_slots_by_user(tx_db, d: date, pool_ids: list[int]) -> dict[int, set[int]]:
    """Слоты вчера по каждому id из пула (для анти-повтора «тот же часовой слот подряд»)."""
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


def _had_same_slot_or_morning_block_yesterday(y_slots: set[int], current_slot: int) -> bool:
    """True, если вчера этот сотрудник уже занимал тот же логический блок слота (утро — оба слота 07–08)."""
    if current_slot == MORNING_FIRST_SLOT_INDEX:
        morning = {MORNING_FIRST_SLOT_INDEX, MORNING_SECOND_SLOT_INDEX}
        return bool(y_slots & morning)
    return current_slot in y_slots


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
    yesterday_slots_by_user: dict[int, set[int]],
    pool_gt_slots: bool,
    current_slot: int,
    rng: random.Random,
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

    prefer_no_repeat = [
        uid
        for uid in eligible
        if not _had_same_slot_or_morning_block_yesterday(yesterday_slots_by_user.get(uid, set()), current_slot)
    ]
    if prefer_no_repeat:
        eligible = prefer_no_repeat

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
    base_users = generation_pool_users(tx_db)
    base_ids = [u.id for u in base_users]
    if not base_ids:
        raise HTTPException(
            status_code=400,
            detail="Нет сотрудников для генерации (support/admin с активными дежурствами, кроме учётной записи bootstrap-админа).",
        )

    min_pool = (SLOT_COUNT + MAX_DUTIES_PER_DAY - 1) // MAX_DUTIES_PER_DAY

    def _pool_ids_for_day(d: date) -> list[int]:
        off = user_ids_on_leave_for_day(tx_db, day=d)
        return [i for i in base_ids if i not in off]

    for day_index in range((end_date - start_date).days + 1):
        current_day = start_date + timedelta(days=day_index)
        if is_non_working_for_duty_generation(current_day):
            continue
        pool_ids = _pool_ids_for_day(current_day)
        if len(pool_ids) < min_pool:
            raise HTTPException(
                status_code=400,
                detail=f"На {current_day.isoformat()} в пуле генерации слишком мало сотрудников "
                f"(нужно не меньше {min_pool}): часть сотрудников отмечена отсутствием в генерации на этот день.",
            )
        pool_ids_set = set(pool_ids)
        resolve_nine_am_user(tx_db, pool_ids_set)

    if overwrite:
        tx_db.execute(
            delete(DutyAssignment).where(
                DutyAssignment.date >= start_date,
                DutyAssignment.date <= end_date,
            )
        )
        tx_db.commit()

    global_counts = {uid: 0 for uid in base_ids}
    for uid in base_ids:
        global_counts[uid] = int(
            tx_db.execute(
                select(func.count())
                .select_from(DutyAssignment)
                .where(DutyAssignment.support_user_id == uid, DutyAssignment.date < start_date)
            ).scalar_one()
        )

    created = 0

    for day_index in range((end_date - start_date).days + 1):
        current_day = start_date + timedelta(days=day_index)
        yesterday = current_day - timedelta(days=1)
        pool_ids = _pool_ids_for_day(current_day)
        pool_ids_set = set(pool_ids)
        nine_user = resolve_nine_am_user(tx_db, pool_ids_set)
        pool_gt_slots = len(pool_ids) > SLOT_COUNT

        yesterday_counts = _yesterday_counts(tx_db, yesterday, pool_ids)
        yesterday_slots_by_user = _yesterday_slots_by_user(tx_db, yesterday, pool_ids)
        day_counts: dict[int, int] = defaultdict(int)

        morning_pair_user_id: int | None = None
        skip_new_assignments = is_non_working_for_duty_generation(current_day)

        tail = [
            s
            for s in range(SLOT_COUNT)
            if s != SLOT_09_00_INDEX and s not in (MORNING_FIRST_SLOT_INDEX, MORNING_SECOND_SLOT_INDEX)
        ]
        rng.shuffle(tail)
        slot_order = [SLOT_09_00_INDEX, MORNING_FIRST_SLOT_INDEX, MORNING_SECOND_SLOT_INDEX] + tail

        for slot in slot_order:
            key = (current_day, slot)
            if (not overwrite) and key in existing_in_range:
                uid = existing_in_range[key]
                if uid in pool_ids_set:
                    day_counts[uid] = day_counts.get(uid, 0) + 1
                    global_counts[uid] = global_counts.get(uid, 0) + 1
                    if slot == MORNING_FIRST_SLOT_INDEX:
                        morning_pair_user_id = uid
                continue

            if skip_new_assignments:
                continue

            if slot == SLOT_09_00_INDEX:
                uid = nine_user.id
            elif slot == MORNING_SECOND_SLOT_INDEX and morning_pair_user_id is not None:
                uid = morning_pair_user_id
            else:
                uid = _pick_user_for_slot(
                    pool_ids,
                    day_counts,
                    global_counts,
                    yesterday_counts,
                    yesterday_slots_by_user,
                    pool_gt_slots,
                    slot,
                    rng,
                )
                if slot == MORNING_FIRST_SLOT_INDEX:
                    morning_pair_user_id = uid

            tx_db.add(DutyAssignment(date=current_day, slot=slot, support_user_id=uid))
            day_counts[uid] = day_counts.get(uid, 0) + 1
            global_counts[uid] = global_counts.get(uid, 0) + 1
            created += 1

        tx_db.flush()

    tx_db.commit()
    return created
