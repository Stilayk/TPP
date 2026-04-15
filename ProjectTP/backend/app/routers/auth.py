from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user, is_bootstrap_admin_account
from app.models import User
from app.schemas import LoginRequest, LogoutOut, SelfChangePasswordRequest, SelfUpdateProfileRequest, UserMeOut
from app.security import hash_password, verify_password

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    return {"ok": True}


@router.post("/api/login", response_model=UserMeOut)
def login(payload: LoginRequest, request: Request, db=Depends(get_db)) -> UserMeOut:
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    request.session["user_id"] = str(user.id)
    return UserMeOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active_for_duties=bool(user.is_active_for_duties),
        is_bootstrap_admin=is_bootstrap_admin_account(user),
        bitrix_user_id=user.bitrix_user_id,
    )


@router.post("/api/logout", response_model=LogoutOut)
def logout(request: Request) -> LogoutOut:
    request.session.clear()
    return LogoutOut(ok=True)


@router.get("/api/me", response_model=UserMeOut)
def me(current_user: User = Depends(get_current_user)) -> UserMeOut:
    return UserMeOut(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active_for_duties=bool(current_user.is_active_for_duties),
        is_bootstrap_admin=is_bootstrap_admin_account(current_user),
        bitrix_user_id=current_user.bitrix_user_id,
    )


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
    return UserMeOut(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active_for_duties=bool(current_user.is_active_for_duties),
        is_bootstrap_admin=is_bootstrap_admin_account(current_user),
        bitrix_user_id=current_user.bitrix_user_id,
    )
