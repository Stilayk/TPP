from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.database import get_db
from app.deps import get_current_user
from app.main import app


def _fake_get_db():
    class _Result:
        def scalars(self):
            return self

        def all(self):
            return [
                SimpleNamespace(bitrix_user_id=10),
                SimpleNamespace(bitrix_user_id=20),
            ]

    db = MagicMock()
    db.execute = MagicMock(return_value=_Result())
    yield db


@patch("app.routers.duties_live.bitrix_im_message_add")
@patch("app.routers.duties_live.bitrix_webhook_base_url")
def test_me_notify_duty_replacement_bitrix_happy(mock_url, mock_add) -> None:
    mock_url.return_value = "https://example.com/rest/1/t/"
    user = SimpleNamespace(
        id=1,
        role="support",
        username="worker",
        full_name="Петров Пётр Петрович",
        bitrix_user_id=11751,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        client = TestClient(app)
        r = client.post("/api/me/duty-replacement-request/bitrix")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"sent": True, "recipients_bitrix": 2}
    assert mock_add.call_count == 2
    dialogs = {call.args[1] for call in mock_add.call_args_list}
    assert dialogs == {"10", "20"}
    message = mock_add.call_args_list[0].args[2]
    assert "Запрос замены дежурства" in message
    assert "11751" in message
