from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.database import get_db
from app.models import User


def is_bootstrap_admin_account(user: User) -> bool:
    """Учётная запись из BOOTSTRAP_ADMIN_* при первом запуске; снятие прав с неё запрещено."""
    from app.config import settings

    name = (settings.BOOTSTRAP_ADMIN_USERNAME or "").strip()
    if not name:
        return False
    return user.username == name


def ensure_support_user(db, user_id: int) -> User:
    u = db.get(User, user_id)
    if not u or u.role != "support":
        raise HTTPException(status_code=400, detail="User is not a support user")
    return u


def get_current_user(request: Request, db=Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = db.get(User, int(user_id))
    if not user:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


def require_support_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("support", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user
