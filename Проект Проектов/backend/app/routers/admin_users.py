from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.deps import ensure_support_user, require_admin
from app.models import DailyReport, ReportEntry, User
from app.schemas import (
    AdminChangePasswordRequest,
    AdminDutyStatusRequest,
    AdminUpdateUserRequest,
    CreateSupportUserRequest,
    UserOut,
)
from app.security import hash_password
from app.services import exports_dir

router = APIRouter()


@router.get("/api/admin/users")
def admin_list_users(current_user: User = Depends(require_admin), db=Depends(get_db)) -> list[UserOut]:
    users = db.execute(select(User).where(User.role == "support").order_by(User.id)).scalars().all()
    return [
        UserOut(
            id=u.id,
            username=u.username,
            full_name=u.full_name,
            role=u.role,
            is_active_for_duties=bool(u.is_active_for_duties),
        )
        for u in users
    ]


@router.post("/api/admin/users", response_model=UserOut)
def admin_create_user(payload: CreateSupportUserRequest, current_user: User = Depends(require_admin), db=Depends(get_db)) -> UserOut:
    user = User(username=payload.username, full_name=payload.full_name, role="support", password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active_for_duties=bool(user.is_active_for_duties),
    )


@router.patch("/api/admin/users/{user_id}/duty-status", response_model=UserOut)
def admin_update_user_duty_status(
    user_id: int,
    payload: AdminDutyStatusRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> UserOut:
    user = ensure_support_user(db, user_id)
    user.is_active_for_duties = payload.is_active_for_duties
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active_for_duties=bool(user.is_active_for_duties),
    )


@router.patch("/api/admin/users/{user_id}", response_model=UserOut)
def admin_update_user_profile(
    user_id: int,
    payload: AdminUpdateUserRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> UserOut:
    user = ensure_support_user(db, user_id)
    user.username = payload.username.strip()
    user.full_name = payload.full_name.strip()
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active_for_duties=bool(user.is_active_for_duties),
    )


@router.post("/api/admin/users/{user_id}/password")
def admin_change_user_password(
    user_id: int,
    payload: AdminChangePasswordRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> dict:
    user = ensure_support_user(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return {"ok": True, "user_id": user.id}


@router.delete("/api/admin/users/{user_id}/reports")
def admin_delete_user_reports(user_id: int, current_user: User = Depends(require_admin), db=Depends(get_db)) -> dict:
    user = ensure_support_user(db, user_id)
    reports = db.execute(
        select(DailyReport.id, DailyReport.date).where(DailyReport.support_user_id == user.id)
    ).all()
    report_ids = [int(report_id) for report_id, _ in reports]

    deleted_entries = 0
    deleted_reports = 0
    if report_ids:
        deleted_entries = int(
            db.execute(delete(ReportEntry).where(ReportEntry.report_id.in_(report_ids))).rowcount or 0
        )
        deleted_reports = int(
            db.execute(delete(DailyReport).where(DailyReport.id.in_(report_ids))).rowcount or 0
        )
        db.commit()

    deleted_exports = 0
    root = exports_dir().resolve()
    for report_id, report_date in reports:
        filename = f"report_{report_id}_{report_date.isoformat()}.xlsx"
        out_path = (root / filename).resolve()
        if out_path.is_file() and str(out_path).startswith(str(root)):
            try:
                out_path.unlink()
                deleted_exports += 1
            except OSError:
                pass

    return {
        "ok": True,
        "user_id": user.id,
        "deleted_reports": deleted_reports,
        "deleted_entries": deleted_entries,
        "deleted_exports": deleted_exports,
    }


@router.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, current_user: User = Depends(require_admin), db=Depends(get_db)) -> dict:
    user = ensure_support_user(db, user_id)
    deleted_user_id = user.id
    db.delete(user)
    db.commit()
    return {"ok": True, "deleted_user_id": deleted_user_id}
