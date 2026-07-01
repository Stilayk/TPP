from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, delete, extract, func, select
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.deps import ensure_support_or_admin_user, get_current_user, user_has_capability
from app.duty_slots import MORNING_SLOT_INDEXES, SLOT_COUNT
from app.models import DailyReport, DutyAssignment, DutySwapRequest, ReportEntry, User
from app.schemas import (
    CreateOrGetReportRequest,
    DailyReportOut,
    DutyAnalyticsEmployeeRowOut,
    DutyAnalyticsMonthRowOut,
    DutyAnalyticsOut,
    DutyAnalyticsOverloadRowOut,
    DutySwapAnalyticsOut,
    ReportFinalizeOut,
    ReportHistoryItemOut,
    UpdateReportRequest,
    UserOut,
)
from app.services import build_report_excel, exports_dir, report_excel_filename, report_to_out

router = APIRouter()


def _utc_now() -> datetime:
    return datetime.utcnow()


def _report_history_item(db, report: DailyReport) -> ReportHistoryItemOut:
    employee = db.get(User, report.support_user_id)
    if not employee:
        raise HTTPException(status_code=500, detail="Employee not found")
    return ReportHistoryItemOut(
        report_id=report.id,
        date=report.date,
        employee_id=report.support_user_id,
        employee=UserOut(
            id=employee.id,
            username=employee.username,
            full_name=employee.full_name,
            role=employee.role,
            is_active_for_duties=bool(employee.is_active_for_duties),
            is_eligible_for_morning_duties=bool(employee.is_eligible_for_morning_duties),
            is_bootstrap_admin=False,
            bitrix_user_id=employee.bitrix_user_id,
        ),
        status=report.status,
        finalized_at=report.finalized_at,
        updated_at=report.updated_at,
    )


def _year_months_inclusive(start_date: date, end_date: date) -> list[str]:
    """Календарные месяцы от месяца start_date до месяца end_date включительно (YYYY-MM)."""
    out: list[str] = []
    y, m = start_date.year, start_date.month
    end_ym = (end_date.year, end_date.month)
    while (y, m) <= end_ym:
        out.append(f"{y:04d}-{m:02d}")
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


def _analytics_employee_slots(db, start_date: date, end_date: date, morning: bool) -> list[DutyAnalyticsEmployeeRowOut]:
    stmt = (
        select(User.id, User.full_name, func.count())
        .join(DutyAssignment, DutyAssignment.support_user_id == User.id)
        .where(DutyAssignment.date >= start_date, DutyAssignment.date <= end_date)
    )
    if morning:
        stmt = stmt.where(DutyAssignment.slot.in_(MORNING_SLOT_INDEXES))
    else:
        stmt = stmt.where(~DutyAssignment.slot.in_(MORNING_SLOT_INDEXES))
    rows = db.execute(
        stmt.group_by(User.id, User.full_name).order_by(func.count().desc(), User.full_name.asc())
    ).all()
    return [
        DutyAnalyticsEmployeeRowOut(user_id=int(uid), full_name=name, slot_count=int(cnt))
        for uid, name, cnt in rows
    ]


def _analytics_overload_warnings(employee_slots: list[DutyAnalyticsEmployeeRowOut], assigned_slots: int) -> list[DutyAnalyticsOverloadRowOut]:
    warnings: list[DutyAnalyticsOverloadRowOut] = []
    if len(employee_slots) < 2 or assigned_slots < 12:
        return warnings
    mean_per = assigned_slots / len(employee_slots)
    threshold = max(mean_per * 1.35, float(math.ceil(mean_per) + 2))
    for row in employee_slots:
        c = int(row.slot_count)
        if c >= threshold:
            share = round(100.0 * c / assigned_slots, 1) if assigned_slots else 0.0
            warnings.append(
                DutyAnalyticsOverloadRowOut(
                    user_id=int(row.user_id),
                    full_name=row.full_name or "",
                    slot_count=c,
                    share_percent=share,
                    note="Значительно выше среднего по периоду",
                )
            )
    return warnings


@router.post("/api/reports", response_model=DailyReportOut)
def create_or_get_report(payload: CreateOrGetReportRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)) -> DailyReportOut:
    target_support_id: int
    can_manage_reports = user_has_capability(current_user, "manage_reports")
    if current_user.role == "support":
        if can_manage_reports and payload.employee_id is not None:
            target_support_id = payload.employee_id
        else:
            target_support_id = current_user.id
            if payload.employee_id is not None and payload.employee_id != current_user.id:
                raise HTTPException(status_code=403, detail="Cannot create report for other employee")
    else:
        if payload.employee_id is None:
            target_support_id = current_user.id
        else:
            target_support_id = payload.employee_id

    employee = ensure_support_or_admin_user(db, target_support_id)

    existing = db.execute(
        select(DailyReport).where(DailyReport.date == payload.date, DailyReport.support_user_id == employee.id)
    ).scalar_one_or_none()

    if existing:
        db.refresh(existing)
        return report_to_out(db, existing)

    now = _utc_now()
    new_report = DailyReport(
        date=payload.date,
        support_user_id=employee.id,
        status="draft",
        finalized_at=None,
        updated_at=now,
    )
    db.add(new_report)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(DailyReport).where(DailyReport.date == payload.date, DailyReport.support_user_id == employee.id)
        ).scalar_one_or_none()
        if not existing:
            raise
        db.refresh(existing)
        return report_to_out(db, existing)
    db.refresh(new_report)
    return report_to_out(db, new_report)


@router.get("/api/reports", response_model=list[DailyReportOut])
def list_reports(
    date_: date = Query(..., alias="date"),
    employee_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> list[DailyReportOut]:
    can_manage_reports = user_has_capability(current_user, "manage_reports")
    if current_user.role == "support":
        if not can_manage_reports:
            if employee_id is not None and employee_id != current_user.id:
                raise HTTPException(status_code=403, detail="Forbidden")
            employee_id = current_user.id
    else:
        if employee_id is not None:
            employee = ensure_support_or_admin_user(db, employee_id)
            employee_id = employee.id

    stmt = select(DailyReport).where(DailyReport.date == date_)
    if employee_id is not None:
        stmt = stmt.where(DailyReport.support_user_id == employee_id)

    reports = db.execute(stmt.order_by(DailyReport.support_user_id)).scalars().all()
    out: list[DailyReportOut] = []
    for r in reports:
        db.refresh(r)
        out.append(report_to_out(db, r))
    return out


@router.get("/api/reports/recent", response_model=list[ReportHistoryItemOut])
def list_recent_reports(
    limit: int = Query(15, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> list[ReportHistoryItemOut]:
    can_manage_reports = user_has_capability(current_user, "manage_reports")
    stmt = select(DailyReport).order_by(DailyReport.updated_at.desc()).limit(limit)
    if current_user.role == "support" and not can_manage_reports:
        stmt = stmt.where(DailyReport.support_user_id == current_user.id)

    reports = db.execute(stmt).scalars().all()
    return [_report_history_item(db, r) for r in reports]


@router.put("/api/reports/{report_id}", response_model=DailyReportOut)
def update_report(
    report_id: int,
    payload: UpdateReportRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> DailyReportOut:
    report = db.get(DailyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    can_manage_reports = user_has_capability(current_user, "manage_reports")
    if current_user.role == "support" and not can_manage_reports and report.support_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    new_date = payload.date or report.date
    new_support_id = payload.employee_id or report.support_user_id

    if user_has_capability(current_user, "manage_reports"):
        if payload.employee_id is not None:
            ensure_support_or_admin_user(db, payload.employee_id)
    else:
        new_date = report.date
        new_support_id = report.support_user_id

    if (new_date != report.date) or (new_support_id != report.support_user_id):
        existing = db.execute(
            select(DailyReport).where(
                DailyReport.date == new_date,
                DailyReport.support_user_id == new_support_id,
                DailyReport.id != report.id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Report for this employee/date already exists")

    report.date = new_date
    report.support_user_id = new_support_id

    report.updated_at = _utc_now()
    db.execute(delete(ReportEntry).where(ReportEntry.report_id == report.id))
    for entry in payload.entries:
        db.add(
            ReportEntry(
                report_id=report.id,
                task=entry.task or "",
                minutes=entry.minutes,
                description=entry.description,
            )
        )

    db.commit()
    filename = report_excel_filename(report)
    out_path = (exports_dir() / filename).resolve()
    if out_path.exists():
        try:
            out_path.unlink()
        except OSError:
            pass
    db.refresh(report)
    return report_to_out(db, report)


@router.post("/api/reports/{report_id}/finalize", response_model=ReportFinalizeOut)
def finalize_report(report_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)) -> ReportFinalizeOut:
    report = db.get(DailyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    can_manage_reports = user_has_capability(current_user, "manage_reports")
    if current_user.role == "support" and not can_manage_reports and report.support_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if report.status == "final":
        filename = report_excel_filename(report)
        out_path = (exports_dir() / filename).resolve()
        if not out_path.exists():
            employee = db.get(User, report.support_user_id)
            if not employee:
                raise HTTPException(status_code=500, detail="Employee not found")
            build_report_excel(report, employee)
        return ReportFinalizeOut(report_id=report.id, status="final", excel_url=f"/exports/{filename}")

    employee = db.get(User, report.support_user_id)
    if not employee:
        raise HTTPException(status_code=500, detail="Employee not found")

    now = _utc_now()
    report.status = "final"
    report.finalized_at = now
    report.updated_at = now
    try:
        build_report_excel(report, employee)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(report)

    filename = report_excel_filename(report)
    return ReportFinalizeOut(report_id=report.id, status="final", excel_url=f"/exports/{filename}")


@router.get("/api/admin/analytics/duties-swaps", response_model=DutyAnalyticsOut)
def admin_duties_swaps_analytics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> DutyAnalyticsOut:
    if not user_has_capability(current_user, "manage_reports"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    day_count = (end_date - start_date).days + 1
    slot_capacity = day_count * SLOT_COUNT
    morning_slot_capacity = day_count * len(MORNING_SLOT_INDEXES)
    regular_slot_capacity = max(slot_capacity - morning_slot_capacity, 0)

    assigned_slots = int(
        db.execute(
            select(func.count())
            .select_from(DutyAssignment)
            .where(DutyAssignment.date >= start_date, DutyAssignment.date <= end_date)
        ).scalar_one()
        or 0
    )
    morning_assigned_slots = int(
        db.execute(
            select(func.count())
            .select_from(DutyAssignment)
            .where(
                DutyAssignment.date >= start_date,
                DutyAssignment.date <= end_date,
                DutyAssignment.slot.in_(MORNING_SLOT_INDEXES),
            )
        ).scalar_one()
        or 0
    )
    regular_assigned_slots = max(assigned_slots - morning_assigned_slots, 0)

    employee_slots = _analytics_employee_slots(db, start_date, end_date, morning=False)
    morning_employee_slots = _analytics_employee_slots(db, start_date, end_date, morning=True)

    ey = extract("year", DutyAssignment.date)
    em = extract("month", DutyAssignment.date)
    assign_month_rows = db.execute(
        select(
            ey,
            em,
            func.count(),
            func.sum(case((DutyAssignment.slot.in_(MORNING_SLOT_INDEXES), 1), else_=0)),
        )
        .where(DutyAssignment.date >= start_date, DutyAssignment.date <= end_date)
        .group_by(ey, em)
        .order_by(ey, em)
    ).all()
    assign_by_month = {}
    morning_assign_by_month = {}
    for r in assign_month_rows:
        ym = f"{int(r[0]):04d}-{int(r[1]):02d}"
        assigned_total = int(r[2] or 0)
        morning_total = int(r[3] or 0)
        assign_by_month[ym] = assigned_total
        morning_assign_by_month[ym] = morning_total

    sy = extract("year", DutySwapRequest.date)
    sm = extract("month", DutySwapRequest.date)
    swap_month_rows = db.execute(
        select(sy, sm, func.count())
        .where(DutySwapRequest.date >= start_date, DutySwapRequest.date <= end_date)
        .group_by(sy, sm)
        .order_by(sy, sm)
    ).all()
    swap_by_month = {f"{int(r[0]):04d}-{int(r[1]):02d}": int(r[2]) for r in swap_month_rows}

    monthly = [
        DutyAnalyticsMonthRowOut(
            year_month=ym,
            assigned_slots=assign_by_month.get(ym, 0),
            regular_assigned_slots=max(assign_by_month.get(ym, 0) - morning_assign_by_month.get(ym, 0), 0),
            morning_assigned_slots=morning_assign_by_month.get(ym, 0),
            swap_requests_total=swap_by_month.get(ym, 0),
        )
        for ym in _year_months_inclusive(start_date, end_date)
    ]

    overload_warnings = _analytics_overload_warnings(employee_slots, regular_assigned_slots)
    morning_overload_warnings = _analytics_overload_warnings(morning_employee_slots, morning_assigned_slots)

    swap_rows = db.execute(
        select(DutySwapRequest.status, func.count())
        .where(DutySwapRequest.date >= start_date, DutySwapRequest.date <= end_date)
        .group_by(DutySwapRequest.status)
    ).all()
    swap_counts = {"pending": 0, "accepted": 0, "rejected": 0}
    for status, cnt in swap_rows:
        if status in swap_counts:
            swap_counts[status] = int(cnt)
    swaps = DutySwapAnalyticsOut(
        total=sum(swap_counts.values()),
        pending=swap_counts["pending"],
        accepted=swap_counts["accepted"],
        rejected=swap_counts["rejected"],
    )

    return DutyAnalyticsOut(
        start_date=start_date,
        end_date=end_date,
        slot_capacity=slot_capacity,
        assigned_slots=assigned_slots,
        unassigned_slots=max(slot_capacity - assigned_slots, 0),
        regular_slot_capacity=regular_slot_capacity,
        regular_assigned_slots=regular_assigned_slots,
        regular_unassigned_slots=max(regular_slot_capacity - regular_assigned_slots, 0),
        morning_slot_capacity=morning_slot_capacity,
        morning_assigned_slots=morning_assigned_slots,
        morning_unassigned_slots=max(morning_slot_capacity - morning_assigned_slots, 0),
        employee_slots=employee_slots,
        morning_employee_slots=morning_employee_slots,
        swaps=swaps,
        monthly=monthly,
        overload_warnings=overload_warnings,
        morning_overload_warnings=morning_overload_warnings,
    )
