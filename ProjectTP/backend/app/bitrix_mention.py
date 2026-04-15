from __future__ import annotations

from app.models import User


def bitrix_im_display_name(user: User) -> str:
    """Строка для текста im.message.add: BB-упоминание [USER=id]…[/USER] или ФИО без привязки."""
    # Логин `user` — служебная строка графика (напр. «Все»); BB-тег гонит уведомление в Битрикс на эту сущность.
    if (user.username or "").strip().lower() == "user":
        return user.full_name or ""
    bid = user.bitrix_user_id
    if bid is not None:
        safe = (user.full_name or "").replace("[", " ").replace("]", " ").strip() or str(bid)
        return f"[USER={int(bid)}]{safe}[/USER]"
    return user.full_name or ""
