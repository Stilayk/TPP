"""Патчит dispatch уведомлений о дежурствах до импорта роутеров (файл duty_notifications.py в репозитории может быть read-only)."""

from __future__ import annotations

from typing import Any, Optional

_applied = False


def apply_monkeypatches() -> None:
    global _applied
    if _applied:
        return
    import app.duty_notifications as dn
    from app import duty_notification_slot as slot_mod

    _orig_dispatch = dn.dispatch_duty_notification

    def dispatch_duty_notification(
        db: Any,
        *,
        mode: str,
        at: Optional[Any] = None,
        invoked_by_scheduler: bool = False,
        strict_timing: bool = True,
    ) -> Any:
        def slot_fn(*, at: Any, offset_minutes: int) -> Any:
            return slot_mod.resolve_notification_slot(
                at=at, offset_minutes=offset_minutes, strict_timing=strict_timing
            )

        prev = dn._resolve_notification_slot
        dn._resolve_notification_slot = slot_fn  # type: ignore[assignment]
        try:
            return _orig_dispatch(db, mode=mode, at=at, invoked_by_scheduler=invoked_by_scheduler)
        finally:
            dn._resolve_notification_slot = prev  # type: ignore[assignment]

    dn.dispatch_duty_notification = dispatch_duty_notification  # type: ignore[assignment]
    _applied = True
