from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import update

from app.models import User

PRESENCE_MIN_INTERVAL = timedelta(minutes=5)


def touch_user_last_seen(db, user_id: int, *, force: bool = False) -> None:
    """Обновить время последней активности (UTC naive), не чаще раза в 5 минут."""
    now = datetime.utcnow()
    if force:
        db.execute(update(User).where(User.id == user_id).values(last_seen_at=now))
        db.commit()
        return
    threshold = now - PRESENCE_MIN_INTERVAL
    result = db.execute(
        update(User)
        .where(User.id == user_id)
        .where((User.last_seen_at.is_(None)) | (User.last_seen_at < threshold))
        .values(last_seen_at=now)
    )
    if result.rowcount:
        db.commit()
