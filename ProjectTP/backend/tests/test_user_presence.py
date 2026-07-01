from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from app.user_presence import PRESENCE_MIN_INTERVAL, touch_user_last_seen


def test_touch_user_last_seen_force_commits() -> None:
    db = MagicMock()
    touch_user_last_seen(db, 7, force=True)
    db.execute.assert_called_once()
    db.commit.assert_called_once()


def test_touch_user_last_seen_skips_commit_when_no_row_updated() -> None:
    db = MagicMock()
    db.execute.return_value = MagicMock(rowcount=0)
    touch_user_last_seen(db, 7)
    db.commit.assert_not_called()


def test_presence_interval_is_five_minutes() -> None:
    assert PRESENCE_MIN_INTERVAL == timedelta(minutes=5)
