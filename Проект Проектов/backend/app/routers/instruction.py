from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.deps import require_support_or_admin
from app.models import User
from app.schemas import EmployeeExitInstructionOut, EmployeeExitInstructionRequest
from app.services import (
    attachment_content_disposition_docx,
    attachment_filename_docx,
    build_employee_exit_instruction,
    build_employee_exit_instruction_docx_bytes,
)

router = APIRouter()


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
    text = build_employee_exit_instruction(payload.fio, payload.login, payload.password, payload.domain)
    return EmployeeExitInstructionOut(text=text)


@router.post("/api/ee_instruction/docx")
@router.post("/api/employee_exit/instruction/docx")
@router.post("/api/employee-exit/instruction/docx")
def employee_exit_instruction_docx(
    payload: EmployeeExitInstructionRequest,
    _user: User = Depends(require_support_or_admin),
) -> Response:
    content = build_employee_exit_instruction_docx_bytes(payload.fio, payload.login, payload.password, payload.domain)
    fname = attachment_filename_docx(payload.fio.strip() or "employee")
    cd = attachment_content_disposition_docx(fname)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": cd},
    )
