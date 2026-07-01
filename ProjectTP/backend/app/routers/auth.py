from __future__ import annotations

import time
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text

from app.database import get_db
from app.deps import get_current_user, is_bootstrap_admin_account
from app.duty_leave_ops import list_leave_dates_from_today
from app.models import User
from app.schemas import (
    LoginRequest,
    LogoutOut,
    SelfChangePasswordRequest,
    SelfUpdateProfileRequest,
    UserMeOut,
    UserPermissionsOut,
)
from app.security import hash_password, verify_password
from app.user_presence import touch_user_last_seen

router = APIRouter()

_LOGIN_FAIL_WINDOW_SEC = 900.0
_LOGIN_FAIL_MAX = 12
_login_fail_lock = Lock()
_login_fail_times: dict[tuple[str, str], list[float]] = {}


def _user_me_out(db, user: User) -> UserMeOut:
    leaves = list_leave_dates_from_today(db, user_id=user.id)
    return UserMeOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active_for_duties=bool(user.is_active_for_duties),
        is_eligible_for_morning_duties=bool(user.is_eligible_for_morning_duties),
        is_bootstrap_admin=is_bootstrap_admin_account(user),
        bitrix_user_id=user.bitrix_user_id,
        permissions=UserPermissionsOut(
            can_manage_duties=bool(user.can_manage_duties),
            can_manage_reports=bool(user.can_manage_reports),
            can_manage_notifications=bool(user.can_manage_notifications),
        ),
        last_seen_at=user.last_seen_at,
        duty_leave_dates=leaves,
    )


def _login_throttle_key(request: Request, username: str) -> tuple[str, str]:
    ip = (request.client.host if request.client else "") or "unknown"
    return (ip, (username or "").lower())


def _login_prune(ts: list[float]) -> list[float]:
    now = time.time()
    return [t for t in ts if now - t < _LOGIN_FAIL_WINDOW_SEC]


def login_is_blocked(request: Request, username: str) -> bool:
    with _login_fail_lock:
        k = _login_throttle_key(request, username)
        arr = _login_prune(_login_fail_times.get(k, []))
        _login_fail_times[k] = arr
        return len(arr) >= _LOGIN_FAIL_MAX


def login_record_failure(request: Request, username: str) -> None:
    with _login_fail_lock:
        k = _login_throttle_key(request, username)
        arr = _login_prune(_login_fail_times.get(k, []))
        arr.append(time.time())
        _login_fail_times[k] = arr


def login_clear_failures(request: Request, username: str) -> None:
    with _login_fail_lock:
        _login_fail_times.pop(_login_throttle_key(request, username), None)


@router.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "projecttp"}


@router.get("/api/ready")
def ready(db=Depends(get_db)) -> dict:
    """Проверка доступности БД (оркестрация readiness)."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"ready": True, "database": True}


@router.post("/api/login", response_model=UserMeOut)
def login(payload: LoginRequest, request: Request, db=Depends(get_db)) -> UserMeOut:
    if login_is_blocked(request, payload.username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много неудачных попыток входа. Подождите до 15 минут.",
        )
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        login_record_failure(request, payload.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    login_clear_failures(request, payload.username)
    request.session["user_id"] = str(user.id)
    touch_user_last_seen(db, user.id, force=True)
    db.refresh(user)
    return _user_me_out(db, user)


@router.post("/api/logout", response_model=LogoutOut)
def logout(request: Request) -> LogoutOut:
    request.session.clear()
    return LogoutOut(ok=True)


@router.get("/api/me", response_model=UserMeOut)
def me(current_user: User = Depends(get_current_user), db=Depends(get_db)) -> UserMeOut:
    touch_user_last_seen(db, current_user.id)
    db.refresh(current_user)
    return _user_me_out(db, current_user)


@router.post("/api/me/presence")
def touch_presence(current_user: User = Depends(get_current_user), db=Depends(get_db)) -> dict:
    """Пинг активности (вкладка открыта); обновление не чаще раза в 5 минут."""
    touch_user_last_seen(db, current_user.id)
    return {"ok": True}


@router.post("/api/me/password")
def change_own_password(
    payload: SelfChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid old password")
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="New password must differ from old password")

    current_user.password_hash = hash_password(payload.new_password)
    db.add(current_user)
    db.commit()
    return {"ok": True}


@router.patch("/api/me/profile", response_model=UserMeOut)
def update_own_profile(
    payload: SelfUpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> UserMeOut:
    current_user.full_name = payload.full_name.strip()
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _user_me_out(db, current_user)
