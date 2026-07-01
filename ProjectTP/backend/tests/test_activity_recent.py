from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db
from app.main import app


def _fake_get_db(swaps):
    db = MagicMock()

    class _Scalars:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    class _Result:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return _Scalars(self._items)

    def execute(stmt):
        if "duty_swap_requests" in str(stmt):
            return _Result(swaps)
        return _Result(
            [
                SimpleNamespace(id=1, full_name="Иванов", username="ivan"),
                SimpleNamespace(id=2, full_name="Петров", username="petr"),
            ]
        )

    db.execute = execute
    yield db


def test_activity_recent_incoming_swap() -> None:
    swap = SimpleNamespace(
        id=5,
        date=date(2026, 5, 20),
        from_slot=2,
        to_slot=4,
        requester_user_id=1,
        target_user_id=2,
        message="Петров, Иванов запрашивает обмен",
        status="pending",
        created_at=datetime(2026, 5, 20, 10, 0, 0),
    )
    user = SimpleNamespace(
        id=2,
        role="support",
        username="petr",
        full_name="Петров",
        can_manage_duties=False,
        can_manage_reports=False,
        can_manage_notifications=False,
    )

    def _override_db():
        yield from _fake_get_db([swap])

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db
    try:
        client = TestClient(app)
        r = client.get("/api/activity/recent?limit=5")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == "swap-5"
    assert body[0]["kind"] == "swap_incoming"
    assert body[0]["status"] == "pending"
    assert "Входящий" in body[0]["title"]
