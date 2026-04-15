from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

SLOT_MAX_INDEX = 10


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class CreateSupportUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)
    bitrix_user_id: Optional[int] = Field(None, ge=1, le=2_147_483_647)


class AdminChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


class AdminDutyStatusRequest(BaseModel):
    is_active_for_duties: bool


class AdminBitrixUserIdRequest(BaseModel):
    """null — сбросить привязку к пользователю Битрикс24."""

    bitrix_user_id: Optional[int] = Field(None, ge=1, le=2_147_483_647)


class AdminUpdateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=200)


class SelfChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class SelfUpdateProfileRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)


class EmployeeExitInstructionRequest(BaseModel):
    fio: str = Field(min_length=1, max_length=300)
    login: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=128)


class EmployeeExitInstructionOut(BaseModel):
    text: str


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active_for_duties: bool = True
    is_bootstrap_admin: bool = False
    bitrix_user_id: Optional[int] = None


class AdminRoleAuditOut(BaseModel):
    id: int
    actor_user_id: int
    target_user_id: int
    action: str
    created_at: datetime


class UserMeOut(UserOut):
    pass


class LogoutOut(BaseModel):
    ok: bool = True


class DutySlotOut(BaseModel):
    slot: int
    start_time: str
    user: Optional[UserOut] = None


class DutiesOut(BaseModel):
    date: date
    slots: list[DutySlotOut]


class DutiesGenerateRequest(BaseModel):
    start_date: date
    end_date: date
    overwrite: bool = False


class DutiesBatchSlot(BaseModel):
    slot: int = Field(ge=0, le=SLOT_MAX_INDEX)
    user_id: int = Field(ge=1)


class DutiesBatchRequest(BaseModel):
    date: date
    assignments: list[DutiesBatchSlot]


class DutySwapCreateRequest(BaseModel):
    date: date
    from_slot: int = Field(ge=0, le=SLOT_MAX_INDEX)
    to_slot: int = Field(ge=0, le=SLOT_MAX_INDEX)


class DutySwapOut(BaseModel):
    id: int
    date: date
    from_slot: int
    to_slot: int
    requester_user_id: int
    target_user_id: int
    message: str
    status: str
    created_at: datetime


class DutySwapDecisionRequest(BaseModel):
    action: str = Field(pattern="^(accept|reject)$")


class ReportEntryIn(BaseModel):
    task: str = Field(default="", max_length=500)
    minutes: int = Field(ge=0, le=24 * 60)
    description: str = Field(min_length=1, max_length=2000)


class CreateOrGetReportRequest(BaseModel):
    date: date
    employee_id: Optional[int] = Field(default=None, ge=1)


class UpdateReportRequest(BaseModel):
    date: Optional[date] = None
    employee_id: Optional[int] = None
    entries: list[ReportEntryIn]


class ReportEntryOut(BaseModel):
    task: str
    minutes: int
    description: str


class DailyReportOut(BaseModel):
    report_id: int
    date: date
    employee_id: int
    employee: UserOut
    status: str
    finalized_at: Optional[datetime] = None
    entries: list[ReportEntryOut] = Field(default_factory=list)


class DutiesGenerateOut(BaseModel):
    start_date: date
    end_date: date
    overwrite: bool
    created_assignments: int


class ReportFinalizeOut(BaseModel):
    report_id: int
    status: str
    excel_url: str


class DutyNotificationDispatchOut(BaseModel):
    sent: bool
    reason: Optional[str] = None
    date: date
    slot: int
    start_time: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    n8n_sent: Optional[bool] = None
    bitrix_sent: Optional[bool] = None


class DutyScheduleBitrixDispatchOut(BaseModel):
    sent: bool
    date: date
