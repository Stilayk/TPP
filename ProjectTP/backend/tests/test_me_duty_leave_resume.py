from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.database import get_db
from app.deps import get_current_user
from app.main import app


@patch("app.routers.me_duty_leave.list_leave_dates_from_today", return_value=[])
@patch("app.routers.me_duty_leave.remove_today_leave_if_present", return_value=True)
def test_me_resume_duty_leave_today_happy(_mock_remove, _mock_list) -> None:
    user = SimpleNamespace(id=3, role="support", username="worker")

    def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _fake_db
    try:
        client = TestClient(app)
        r = client.post("/api/me/duty-leave-dates/resume-today")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"dates": []}
