from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.database import get_db
from app.deps import get_current_user
from app.main import app


def _fake_get_db():
    assignment = SimpleNamespace(slot=0)
    user = SimpleNamespace(full_name="Иванов И.", username="ivan", bitrix_user_id=10)

    class _Result:
        def all(self):
            return [(assignment, user)]

    db = MagicMock()
    db.execute = MagicMock(return_value=_Result())
    yield db


@patch("app.routers.duties_live.bitrix_im_message_add")
@patch("app.routers.duties_live.bitrix_messaging_pair_for_chat", return_value=("https://example.com/rest/1/t/", "chat1"))
def test_duty_schedule_bitrix_manage_duties_happy(mock_pair, mock_add) -> None:
    user = SimpleNamespace(
        id=2,
        role="support",
        username="mgr",
        full_name="Менеджер",
        can_manage_duties=True,
        can_manage_reports=False,
        can_manage_notifications=False,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        client = TestClient(app)
        r = client.post("/api/admin/notifications/duty-schedule/bitrix?date=2026-05-15")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"sent": True, "date": "2026-05-15"}
    mock_add.assert_called_once()
    assert "2026-05-15" in mock_add.call_args.args[2]
