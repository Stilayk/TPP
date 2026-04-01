from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.deps import ensure_support_user, get_current_user
from app.models import DailyReport, ReportEntry, User
from app.schemas import CreateOrGetReportRequest, DailyReportOut, ReportFinalizeOut, UpdateReportRequest
from app.services import build_report_excel, exports_dir, report_excel_filename, report_to_out

router = APIRouter()


@router.post("/api/reports", response_model=DailyReportOut)
def create_or_get_report(payload: CreateOrGetReportRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)) -> DailyReportOut:
    target_support_id: int
    if current_user.role == "support":
        target_support_id = current_user.id
        if payload.employee_id is not None and payload.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Cannot create report for other employee")
    else:
        if payload.employee_id is None:
            target_support_id = current_user.id
        else:
            target_support_id = payload.employee_id

    employee = ensure_support_user(db, target_support_id)

    existing = db.execute(
        select(DailyReport).where(DailyReport.date == payload.date, DailyReport.support_user_id == employee.id)
    ).scalar_one_or_none()

    if existing:
        db.refresh(existing)
        return report_to_out(db, existing)

    new_report = DailyReport(date=payload.date, support_user_id=employee.id, status="draft", finalized_at=None)
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
    if current_user.role == "support":
        if employee_id is not None and employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        employee_id = current_user.id
    else:
        if employee_id is not None:
            employee = ensure_support_user(db, employee_id)
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

    if current_user.role == "support" and report.support_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    new_date = payload.date or report.date
    new_support_id = payload.employee_id or report.support_user_id

    if current_user.role == "admin":
        if payload.employee_id is not None:
            ensure_support_user(db, payload.employee_id)
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

    db.execute(delete(ReportEntry).where(ReportEntry.report_id == report.id))
    for entry in payload.entries:
        db.add(ReportEntry(report_id=report.id, minutes=entry.minutes, description=entry.description))

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

    if current_user.role == "support" and report.support_user_id != current_user.id:
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

    report.status = "final"
    report.finalized_at = datetime.utcnow()
    try:
        build_report_excel(report, employee)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(report)

    filename = report_excel_filename(report)
    return ReportFinalizeOut(report_id=report.id, status="final", excel_url=f"/exports/{filename}")
