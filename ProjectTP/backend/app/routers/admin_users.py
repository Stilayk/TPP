from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.deps import (
    ensure_support_or_admin_user,
    is_bootstrap_admin_account,
    require_admin,
    require_admin_or_any_capability,
)
from app.duty_leave_ops import leave_dates_map_from_today, list_leave_dates_from_today
from app.models import AdminRoleAudit, DailyReport, DutySwapRequest, ReportEntry, User
from app.schemas import (
    AdminBitrixUserIdRequest,
    AdminChangePasswordRequest,
    AdminDutyStatusRequest,
    AdminRoleAuditOut,
    AdminUpdateUserRequest,
    AdminUpdateUserPermissionsRequest,
    CreateSupportUserRequest,
    UserPermissionsOut,
    UserOut,
)
from app.security import hash_password
from app.services import exports_dir

router = APIRouter()


def _user_out(u: User, duty_leave_dates: list | None = None) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        full_name=u.full_name,
        role=u.role,
        is_active_for_duties=bool(u.is_active_for_duties),
        is_eligible_for_morning_duties=bool(u.is_eligible_for_morning_duties),
        is_bootstrap_admin=is_bootstrap_admin_account(u),
        bitrix_user_id=u.bitrix_user_id,
        permissions=UserPermissionsOut(
            can_manage_duties=bool(u.can_manage_duties),
            can_manage_reports=bool(u.can_manage_reports),
            can_manage_notifications=bool(u.can_manage_notifications),
        ),
        last_seen_at=u.last_seen_at,
        duty_leave_dates=list(duty_leave_dates or []),
    )


@router.get("/api/admin/users")
def admin_list_users(current_user: User = Depends(require_admin_or_any_capability), db=Depends(get_db)) -> list[UserOut]:
    users = db.execute(select(User).order_by(User.role.desc(), User.id)).scalars().all()
    lm = leave_dates_map_from_today(db, [u.id for u in users])
    return [_user_out(u, lm.get(u.id, [])) for u in users]


@router.get("/api/admin/role-audit", response_model=list[AdminRoleAuditOut])
def admin_list_role_audit(
    limit: int = 50,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> list[AdminRoleAuditOut]:
    lim = min(max(limit, 1), 200)
    rows = (
        db.execute(select(AdminRoleAudit).order_by(AdminRoleAudit.created_at.desc()).limit(lim)).scalars().all()
    )
    return [
        AdminRoleAuditOut(
            id=r.id,
            actor_user_id=r.actor_user_id,
            target_user_id=r.target_user_id,
            action=r.action,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/api/admin/users", response_model=UserOut)
def admin_create_user(payload: CreateSupportUserRequest, current_user: User = Depends(require_admin), db=Depends(get_db)) -> UserOut:
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        role="support",
        password_hash=hash_password(payload.password),
        bitrix_user_id=payload.bitrix_user_id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return _user_out(user, list_leave_dates_from_today(db, user_id=user.id))


@router.post("/api/admin/users/{user_id}/grant-admin", response_model=UserOut)
def admin_grant_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> UserOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "support":
        raise HTTPException(status_code=400, detail="Only support users can be promoted to admin")
    user.role = "admin"
    db.add(user)
    db.add(
        AdminRoleAudit(
            actor_user_id=current_user.id,
            target_user_id=user.id,
            action="grant",
        )
    )
    db.commit()
    db.refresh(user)
    return _user_out(user, list_leave_dates_from_today(db, user_id=user.id))


@router.post("/api/admin/users/{user_id}/revoke-admin", response_model=UserOut)
def admin_revoke_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> UserOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "admin":
        raise HTTPException(status_code=400, detail="User is not an admin")
    if is_bootstrap_admin_account(user):
        raise HTTPException(
            status_code=400,
            detail="Cannot revoke admin rights from the bootstrap administrator",
        )
    admin_count = int(
        db.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar_one()
    )
    if admin_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last admin")
    user.role = "support"
    db.add(user)
    db.add(
        AdminRoleAudit(
            actor_user_id=current_user.id,
            target_user_id=user.id,
            action="revoke",
        )
    )
    db.commit()
    db.refresh(user)
    return _user_out(user, list_leave_dates_from_today(db, user_id=user.id))


@router.patch("/api/admin/users/{user_id}/bitrix-user", response_model=UserOut)
def admin_update_bitrix_user_id(
    user_id: int,
    payload: AdminBitrixUserIdRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> UserOut:
    user = ensure_support_or_admin_user(db, user_id)
    user.bitrix_user_id = payload.bitrix_user_id
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user, list_leave_dates_from_today(db, user_id=user.id))


@router.patch("/api/admin/users/{user_id}/duty-status", response_model=UserOut)
def admin_update_user_duty_status(
    user_id: int,
    payload: AdminDutyStatusRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> UserOut:
    user = ensure_support_or_admin_user(db, user_id)
    if payload.is_eligible_for_morning_duties and not payload.is_active_for_duties:
        raise HTTPException(
            status_code=400,
            detail="Нельзя включить утренние дежурства без участия в генерации графика.",
        )
    user.is_active_for_duties = payload.is_active_for_duties
    if not payload.is_active_for_duties:
        user.is_eligible_for_morning_duties = False
    elif payload.is_eligible_for_morning_duties is not None:
        user.is_eligible_for_morning_duties = payload.is_eligible_for_morning_duties
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user, list_leave_dates_from_today(db, user_id=user.id))


@router.patch("/api/admin/users/{user_id}", response_model=UserOut)
def admin_update_user_profile(
    user_id: int,
    payload: AdminUpdateUserRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> UserOut:
    user = ensure_support_or_admin_user(db, user_id)
    user.username = payload.username.strip()
    user.full_name = payload.full_name.strip()
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return _user_out(user, list_leave_dates_from_today(db, user_id=user.id))


@router.patch("/api/admin/users/{user_id}/permissions", response_model=UserOut)
def admin_update_user_permissions(
    user_id: int,
    payload: AdminUpdateUserPermissionsRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> UserOut:
    user = ensure_support_or_admin_user(db, user_id)
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Permissions for admin users are always full")
    user.can_manage_duties = bool(payload.can_manage_duties)
    user.can_manage_reports = bool(payload.can_manage_reports)
    user.can_manage_notifications = bool(payload.can_manage_notifications)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user, list_leave_dates_from_today(db, user_id=user.id))


@router.post("/api/admin/users/{user_id}/password")
def admin_change_user_password(
    user_id: int,
    payload: AdminChangePasswordRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> dict:
    user = ensure_support_or_admin_user(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return {"ok": True, "user_id": user.id}


@router.delete("/api/admin/users/{user_id}/reports")
def admin_delete_user_reports(user_id: int, current_user: User = Depends(require_admin), db=Depends(get_db)) -> dict:
    user = ensure_support_or_admin_user(db, user_id)
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
    user = ensure_support_or_admin_user(db, user_id)
    if is_bootstrap_admin_account(user):
        raise HTTPException(status_code=400, detail="Cannot delete the bootstrap administrator")
    deleted_user_id = user.id
    db.execute(
        delete(AdminRoleAudit).where(
            or_(
                AdminRoleAudit.target_user_id == deleted_user_id,
                AdminRoleAudit.actor_user_id == deleted_user_id,
            )
        )
    )
    db.execute(
        delete(DutySwapRequest).where(
            or_(
                DutySwapRequest.requester_user_id == deleted_user_id,
                DutySwapRequest.target_user_id == deleted_user_id,
            )
        )
    )
    db.delete(user)
    db.commit()
    return {"ok": True, "deleted_user_id": deleted_user_id}
