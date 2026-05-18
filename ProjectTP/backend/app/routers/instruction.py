from __future__ import annotations

import html
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.deps import require_support_or_admin
from app.models import EmployeeExitInstructionShare, User
from app.schemas import (
    EmployeeExitInstructionOut,
    EmployeeExitInstructionRequest,
    EmployeeExitShareOut,
    EmployeeExitShareRequest,
)
from app.services import (
    attachment_content_disposition_docx,
    attachment_filename_docx,
    build_employee_exit_instruction,
    build_employee_exit_instruction_docx_bytes,
    build_qrcode_png_bytes,
)

router = APIRouter()


def _resolve_public_base_url(request: Request, override: str | None) -> str:
    if override and override.strip():
        u = override.strip().rstrip("/")
        if not (u.startswith("http://") or u.startswith("https://")):
            raise HTTPException(status_code=400, detail="public_base_url must start with http:// or https://")
        if len(u) > 400:
            raise HTTPException(status_code=400, detail="public_base_url too long")
        return u
    xf_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    xf_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    host = xf_host or request.headers.get("host") or ""
    if not host:
        raise HTTPException(
            status_code=400,
            detail="Передайте public_base_url (полный origin приложения, без пути /p/ee/...).",
        )
    scheme = (xf_proto or request.url.scheme or "https").lower()
    if scheme not in ("http", "https"):
        scheme = "https"
    return f"{scheme}://{host}".rstrip("/")


@router.get("/api/employee_exit/ping")
@router.get("/api/ee_instruction/ping")
def employee_exit_ping() -> dict:
    return {"ok": True, "employee_exit": True}


@router.post("/api/ee_instruction", response_model=EmployeeExitInstructionOut)
@router.post("/api/employee_exit/instruction", response_model=EmployeeExitInstructionOut)
@router.post("/api/employee-exit/instruction", response_model=EmployeeExitInstructionOut)
def employee_exit_instruction(
    payload: EmployeeExitInstructionRequest,
    _user: User = Depends(require_support_or_admin),
) -> EmployeeExitInstructionOut:
    text = build_employee_exit_instruction(
        payload.fio, payload.login, payload.password, payload.domain, blocks=payload.blocks
    )
    return EmployeeExitInstructionOut(text=text)


@router.post("/api/ee_instruction/share", response_model=EmployeeExitShareOut)
@router.post("/api/employee_exit/share", response_model=EmployeeExitShareOut)
def employee_exit_instruction_share(
    payload: EmployeeExitShareRequest,
    request: Request,
    _user: User = Depends(require_support_or_admin),
    db=Depends(get_db),
) -> EmployeeExitShareOut:
    text = build_employee_exit_instruction(
        payload.fio, payload.login, payload.password, payload.domain, blocks=payload.blocks
    )
    base = _resolve_public_base_url(request, payload.public_base_url)
    token = secrets.token_urlsafe(32)
    public_url = f"{base}/p/ee/{token}"
    ttl = max(60, int(settings.EE_INSTRUCTION_SHARE_TTL_SECONDS))
    now = datetime.now(timezone.utc)
    row = EmployeeExitInstructionShare(
        token=token,
        body_text=text,
        public_view_url=public_url,
        expires_at=now + timedelta(seconds=ttl),
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return EmployeeExitShareOut(token=token, public_url=public_url, expires_at=row.expires_at, ttl_seconds=ttl)


@router.get("/p/ee/{token}")
def employee_exit_public_view(token: str, db=Depends(get_db)) -> Response:
    row = db.execute(
        select(EmployeeExitInstructionShare).where(EmployeeExitInstructionShare.token == token)
    ).scalar_one_or_none()
    if row is None:
        return Response(
            content="<html lang='ru'><meta charset='utf-8'/><body><p>Ссылка недействительна.</p></body></html>",
            media_type="text/html; charset=utf-8",
            status_code=404,
        )
    if datetime.now(timezone.utc) > row.expires_at:
        return Response(
            content="<html lang='ru'><meta charset='utf-8'/><body><p>Срок действия ссылки истёк.</p></body></html>",
            media_type="text/html; charset=utf-8",
            status_code=410,
        )
    safe = html.escape(row.body_text)
    page = (
        "<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\"/>"
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        "<title>Инструкция</title></head><body>"
        f'<pre style="white-space:pre-wrap;font-family:system-ui,sans-serif">{safe}</pre>'
        "</body></html>"
    )
    return Response(content=page, media_type="text/html; charset=utf-8")


@router.get("/api/ee_instruction/qr/{token}")
def employee_exit_instruction_qr_png(
    token: str,
    _user: User = Depends(require_support_or_admin),
    db=Depends(get_db),
) -> Response:
    row = db.execute(
        select(EmployeeExitInstructionShare).where(EmployeeExitInstructionShare.token == token)
    ).scalar_one_or_none()
    if row is None or datetime.now(timezone.utc) > row.expires_at:
        raise HTTPException(status_code=404, detail="Токен не найден или срок ссылки истёк")
    png = build_qrcode_png_bytes(row.public_view_url)
    return Response(content=png, media_type="image/png")


@router.post("/api/ee_instruction/docx")
@router.post("/api/employee_exit/instruction/docx")
@router.post("/api/employee-exit/instruction/docx")
def employee_exit_instruction_docx(
    payload: EmployeeExitInstructionRequest,
    _user: User = Depends(require_support_or_admin),
) -> Response:
    content = build_employee_exit_instruction_docx_bytes(
        payload.fio, payload.login, payload.password, payload.domain, blocks=payload.blocks
    )
    fname = attachment_filename_docx(payload.fio.strip() or "employee")
    cd = attachment_content_disposition_docx(fname)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": cd},
    )
