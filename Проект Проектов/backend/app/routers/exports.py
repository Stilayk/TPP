from __future__ import annotations

import io
import zipfile
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import DailyReport, User
from app.services import (
    EXPORT_FILENAME_RE,
    build_report_excel,
    exports_dir,
    is_safe_export_filename,
    report_excel_filename,
    safe_export_name_part,
    surname_from_full_name,
)

router = APIRouter()


@router.get("/exports/{filename}")
def download_export(filename: str, current_user: User = Depends(get_current_user), db=Depends(get_db)) -> FileResponse:
    if not is_safe_export_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    m = EXPORT_FILENAME_RE.match(filename)
    if not m:
        raise HTTPException(status_code=404, detail="Not found")

    report_id = int(m.group(1))
    report = db.get(DailyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Not found")

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    if report.status != "final":
        raise HTTPException(status_code=404, detail="Not finalized")

    out_path = (exports_dir() / filename).resolve()
    root = exports_dir().resolve()
    try:
        if not out_path.is_relative_to(root):
            raise HTTPException(status_code=400, detail="Invalid path")
    except AttributeError:  # pragma: no cover
        if str(root) not in str(out_path):
            raise HTTPException(status_code=400, detail="Invalid path")

    if not out_path.exists():
        employee = db.get(User, report.support_user_id)
        if not employee:
            raise HTTPException(status_code=500, detail="Employee not found")
        build_report_excel(report, employee)
        if not out_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=str(out_path), filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/api/admin/reports/export-all")
def admin_export_all_reports_excel(
    date_: date = Query(..., alias="date"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> StreamingResponse:
    support_users = db.execute(select(User).where(User.role == "support").order_by(User.id)).scalars().all()
    reports = db.execute(select(DailyReport).where(DailyReport.date == date_)).scalars().all()
    by_user_id = {r.support_user_id: r for r in reports}

    missing_employees: list[str] = []
    zip_buffer = io.BytesIO()
    used_names: set[str] = set()
    included = 0

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for user in support_users:
            report = by_user_id.get(user.id)
            if not report or report.status != "final":
                missing_employees.append(user.full_name)
                continue

            filename = report_excel_filename(report)
            out_path = (exports_dir() / filename).resolve()
            if not out_path.exists():
                build_report_excel(report, user)
            if not out_path.exists():
                missing_employees.append(user.full_name)
                continue

            surname = safe_export_name_part(surname_from_full_name(user.full_name))
            base_name = f"{surname} {date_.isoformat()}"
            arcname = f"{base_name}.xlsx"
            if arcname in used_names:
                arcname = f"{base_name} ({user.id}).xlsx"
            used_names.add(arcname)
            zf.writestr(arcname, out_path.read_bytes())
            included += 1

    if included == 0:
        raise HTTPException(status_code=400, detail="Нет сформированных Excel-файлов на выбранную дату")

    zip_buffer.seek(0)
    bundle_name = f"excel_reports_{date_.isoformat()}.zip"
    headers = {
        "Content-Disposition": f'attachment; filename="{bundle_name}"',
        "X-Missing-Employees": quote(",".join(missing_employees)),
        "X-Included-Count": str(included),
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
