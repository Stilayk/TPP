from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.deps import get_current_user, get_db
from app.main import app


def _fake_get_db(reports):
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

    def execute(_stmt):
        return _Result(reports)

    db.execute = execute
    db.get = MagicMock(
        side_effect=lambda _model, uid: SimpleNamespace(
            id=uid,
            username="ivan",
            full_name="Иванов И. И.",
            role="support",
            is_active_for_duties=True,
            bitrix_user_id=None,
        )
    )
    yield db


def test_reports_recent_happy() -> None:
    report = SimpleNamespace(
        id=1,
        date=date(2026, 5, 15),
        support_user_id=2,
        status="final",
        finalized_at=datetime(2026, 5, 15, 9, 28, 0),
        updated_at=datetime(2026, 5, 15, 9, 28, 0),
    )
    user = SimpleNamespace(
        id=2,
        role="support",
        username="ivan",
        full_name="Иванов",
        can_manage_duties=False,
        can_manage_reports=False,
        can_manage_notifications=False,
    )

    def _override_db():
        yield from _fake_get_db([report])

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db
    try:
        client = TestClient(app)
        r = client.get("/api/reports/recent?limit=5")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["report_id"] == 1
    assert body[0]["status"] == "final"
    assert body[0]["employee"]["full_name"] == "Иванов И. И."
