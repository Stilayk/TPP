"""Единый эталон времени для графика дежурств и уведомлений: Europe/Moscow.

Расчёт слотов и триггеров (:55, :00) не должен зависеть от часового пояса браузера пользователя
или случайного TZ хоста без явной настройки — используется московское локальное время.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def now_moscow() -> datetime:
    """Текущий момент в часовом поясе Europe/Moscow (timezone-aware)."""
    return datetime.now(MOSCOW_TZ)


def today_moscow() -> date:
    """Календарная дата по московскому времени."""
    return now_moscow().date()


def anchor_dispatch_at(at: datetime | None) -> datetime:
    """Якорь для расчёта слота уведомления.

    - ``None`` — текущее время по МСК.
    - naive datetime — трактуется как локальное время МСК (ручной вызов API / тесты).
    - aware datetime — переводится в Europe/Moscow.
    """
    if at is None:
        return now_moscow()
    if at.tzinfo is None:
        return at.replace(tzinfo=MOSCOW_TZ)
    return at.astimezone(MOSCOW_TZ)
