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
    is_eligible_for_morning_duties: Optional[bool] = None


class AdminBitrixUserIdRequest(BaseModel):
    """null — сбросить привязку к пользователю Битрикс24."""

    bitrix_user_id: Optional[int] = Field(None, ge=1, le=2_147_483_647)


class AdminUpdateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=200)


class UserPermissionsOut(BaseModel):
    can_manage_duties: bool = False
    can_manage_reports: bool = False
    can_manage_notifications: bool = False


class AdminUpdateUserPermissionsRequest(BaseModel):
    can_manage_duties: bool
    can_manage_reports: bool
    can_manage_notifications: bool


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
    blocks: Optional[list[str]] = Field(
        default=None,
        description="Идентификаторы блоков; не передано — полная инструкция",
    )


class EmployeeExitInstructionOut(BaseModel):
    text: str


class EmployeeExitShareRequest(EmployeeExitInstructionRequest):
    """Те же поля, что для генерации текста; public_base_url — схема+хост+опциональный префикс приложения (без /p/...)."""

    public_base_url: Optional[str] = Field(default=None, max_length=400)


class EmployeeExitShareOut(BaseModel):
    token: str
    public_url: str
    expires_at: datetime
    ttl_seconds: int


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active_for_duties: bool = True
    is_eligible_for_morning_duties: bool = True
    is_bootstrap_admin: bool = False
    bitrix_user_id: Optional[int] = None
    permissions: UserPermissionsOut = Field(default_factory=UserPermissionsOut)
    last_seen_at: Optional[datetime] = None
    duty_leave_dates: list[date] = Field(default_factory=list)


class AdminRoleAuditOut(BaseModel):
    id: int
    actor_user_id: int
    target_user_id: int
    action: str
    created_at: datetime


class UserMeOut(UserOut):
    pass


class DutyLeaveDatesOut(BaseModel):
    dates: list[date]


class DutyLeaveDatesPutRequest(BaseModel):
    dates: list[date] = Field(default_factory=list)


class DutyLeaveDatesCancelOut(BaseModel):
    ok: bool = True
    removed: int = 0


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
    user_id: int | None = None


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


class DutyAnalyticsEmployeeRowOut(BaseModel):
    user_id: int
    full_name: str
    slot_count: int


class DutyAnalyticsMonthRowOut(BaseModel):
    year_month: str
    assigned_slots: int
    regular_assigned_slots: int = 0
    morning_assigned_slots: int = 0
    swap_requests_total: int


class DutyAnalyticsOverloadRowOut(BaseModel):
    user_id: int
    full_name: str
    slot_count: int
    share_percent: float
    note: str


class DutySwapAnalyticsOut(BaseModel):
    total: int
    pending: int
    accepted: int
    rejected: int


class DutyAnalyticsOut(BaseModel):
    start_date: date
    end_date: date
    slot_capacity: int
    assigned_slots: int
    unassigned_slots: int
    regular_slot_capacity: int = 0
    regular_assigned_slots: int = 0
    regular_unassigned_slots: int = 0
    morning_slot_capacity: int = 0
    morning_assigned_slots: int = 0
    morning_unassigned_slots: int = 0
    employee_slots: list[DutyAnalyticsEmployeeRowOut]
    morning_employee_slots: list[DutyAnalyticsEmployeeRowOut] = Field(default_factory=list)
    swaps: DutySwapAnalyticsOut
    monthly: list[DutyAnalyticsMonthRowOut] = Field(default_factory=list)
    overload_warnings: list[DutyAnalyticsOverloadRowOut] = Field(default_factory=list)
    morning_overload_warnings: list[DutyAnalyticsOverloadRowOut] = Field(default_factory=list)


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
    updated_at: Optional[datetime] = None
    entries: list[ReportEntryOut] = Field(default_factory=list)


class ReportHistoryItemOut(BaseModel):
    report_id: int
    date: date
    employee_id: int
    employee: UserOut
    status: str
    finalized_at: Optional[datetime] = None
    updated_at: datetime


class DutiesGenerateOut(BaseModel):
    start_date: date
    end_date: date
    overwrite: bool
    created_assignments: int


class DutiesCopyRangeRequest(BaseModel):
    source_start_date: date
    source_end_date: date
    target_start_date: date
    target_end_date: date
    overwrite: bool = False


class DutiesCopyRangeOut(BaseModel):
    days_copied: int
    created: int
    updated: int
    deleted: int


class ReportFinalizeOut(BaseModel):
    report_id: int
    status: str
    excel_url: str


class DutyNotificationDispatchOut(BaseModel):
    sent: bool
    reason: Optional[str] = None
    event: Optional[str] = None
    date: date
    slot: int
    start_time: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    employee_bitrix_user_id: Optional[int] = None
    n8n_sent: Optional[bool] = None
    bitrix_personal_sent: Optional[bool] = None
    bitrix_chat_sent: Optional[bool] = None


class DutyNotificationSettingsOut(BaseModel):
    """Единый набор флагов (хранение в БД по-прежнему дублируется в cron_* / n8n_* для совместимости)."""

    scheduler_enabled: bool
    enabled_upcoming_5m: bool
    enabled_start: bool
    enabled_chat_on_start: bool


class DutyNotificationSettingsUpdateRequest(BaseModel):
    scheduler_enabled: bool
    enabled_upcoming_5m: bool
    enabled_start: bool
    enabled_chat_on_start: bool


class DutyNotificationTemplatesOut(BaseModel):
    upcoming_5m_template: str
    start_personal_template: str
    start_chat_template: str
    test_with_slot_template: str
    test_without_slot_template: str


class DutyNotificationTemplatesUpdateRequest(BaseModel):
    upcoming_5m_template: str = Field(min_length=1, max_length=2000)
    start_personal_template: str = Field(min_length=1, max_length=2000)
    start_chat_template: str = Field(min_length=1, max_length=2000)
    test_with_slot_template: str = Field(min_length=1, max_length=2000)
    test_without_slot_template: str = Field(min_length=1, max_length=2000)


class DutyTestNotificationOut(BaseModel):
    sent: bool
    reason: Optional[str] = None
    user_id: int
    full_name: str
    message: str
    bitrix_personal_sent: bool


class DutyScheduleBitrixDispatchOut(BaseModel):
    sent: bool
    date: date


class DutyReplacementBitrixNotifyOut(BaseModel):
    sent: bool
    recipients_bitrix: int


class UsefulResourceOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    url: str
    image: str
    color: str
    categories: list[str]
    sort_order: int


class UsefulResourceCategoriesUpdate(BaseModel):
    categories: list[str] = Field(min_length=1)


class RecentActivityItemOut(BaseModel):
    id: str
    kind: str
    title: str
    detail: str
    at: datetime
    status: str | None = None
