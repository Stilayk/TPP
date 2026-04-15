from __future__ import annotations

from app.bitrix_mention import bitrix_im_display_name
from app.models import User


def test_bitrix_im_display_name_without_bitrix() -> None:
    u = User(username="a", full_name="Иванов И.", role="support", password_hash="x")
    assert bitrix_im_display_name(u) == "Иванов И."


def test_bitrix_im_display_name_with_bbcode() -> None:
    u = User(username="a", full_name="Петров П.", role="support", password_hash="x", bitrix_user_id=6188)
    assert bitrix_im_display_name(u) == "[USER=6188]Петров П.[/USER]"


def test_bitrix_im_display_name_admin_with_bbcode() -> None:
    u = User(username="adm", full_name="Админ А.", role="admin", password_hash="x", bitrix_user_id=999)
    assert bitrix_im_display_name(u) == "[USER=999]Админ А.[/USER]"


def test_bitrix_im_display_name_technical_user_login_no_bbcode() -> None:
    u = User(username="user", full_name="Все", role="support", password_hash="x", bitrix_user_id=441509)
    assert bitrix_im_display_name(u) == "Все"
