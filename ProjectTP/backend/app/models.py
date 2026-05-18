from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # "admin" | "support"
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active_for_duties: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Тонкие права для делегирования без роли admin.
    can_manage_duties: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_manage_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_manage_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # ID пользователя Битрикс24 для упоминаний [USER=id] в чате; не секрет
    bitrix_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Успешный POST /api/login (UTC naive, как остальные datetime в проекте)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    duty_assignments: Mapped[list["DutyAssignment"]] = relationship(
        back_populates="support_user", cascade="all,delete"
    )
    reports: Mapped[list["DailyReport"]] = relationship(back_populates="support_user", cascade="all,delete")


class DutyParticipationLeave(Base):
    """Календарные дни, когда сотрудник не участвует в автогенерации графика (отгул от пула)."""

    __tablename__ = "duty_participation_leave"
    __table_args__ = (UniqueConstraint("user_id", "leave_date", name="uq_duty_leave_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AdminRoleAudit(Base):
    __tablename__ = "admin_role_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # "grant" | "revoke"
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (CheckConstraint("action IN ('grant','revoke')", name="ck_admin_role_audit_action"),)


class DutyAssignment(Base):
    __tablename__ = "duty_assignments"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    support_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        CheckConstraint("slot >= 0 AND slot <= 10", name="ck_duty_slot_range"),
    )

    support_user: Mapped[User] = relationship(back_populates="duty_assignments")


class DutySwapRequest(Base):
    __tablename__ = "duty_swap_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    from_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    to_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint("from_slot >= 0 AND from_slot <= 10", name="ck_swap_from_slot_range"),
        CheckConstraint("to_slot >= 0 AND to_slot <= 10", name="ck_swap_to_slot_range"),
        CheckConstraint("status IN ('pending','accepted','rejected')", name="ck_swap_status"),
    )


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    support_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    support_user: Mapped[User] = relationship(back_populates="reports")
    entries: Mapped[list["ReportEntry"]] = relationship(
        back_populates="report", cascade="all,delete-orphan", order_by="ReportEntry.id"
    )

    __table_args__ = (  # type: ignore[assignment]
        UniqueConstraint("date", "support_user_id", name="uq_daily_report_date_employee"),
        CheckConstraint("status IN ('draft','final')", name="ck_daily_report_status"),
    )


class ReportEntry(Base):
    __tablename__ = "report_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("daily_reports.id"), nullable=False, index=True)
    task: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)

    report: Mapped[DailyReport] = relationship(back_populates="entries")


class DutyNotificationSettings(Base):
    __tablename__ = "duty_notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Встроенный планировщик backend (APScheduler): вызовы :55 и :00 по TZ процесса
    scheduler_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    selected_method: Mapped[str] = mapped_column(String(8), nullable=False, default="cron")

    cron_enabled_upcoming_5m: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cron_enabled_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cron_enabled_chat_on_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    n8n_enabled_upcoming_5m: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    n8n_enabled_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    n8n_enabled_chat_on_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    upcoming_5m_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Через 5 минут начинается ваше дежурство: {start_time}, дата {date}.",
    )
    start_personal_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Ваше дежурство началось: {start_time}, дата {date}.",
    )
    start_chat_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="На следующий час дежурным заступает {employee}, слот {start_time}, дата {date}.",
    )
    test_with_slot_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=(
            "Уведомление: сегодня ваше дежурство в {start_time}. "
            "Хорошего вам дня. Обнял, приподнял, покружил, поставил."
        ),
    )
    test_without_slot_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=(
            "Уведомление: на сегодня у вас нет слота в графике дежурств. "
            "Хорошего вам дня. Обнял, приподнял, покружил, поставил."
        ),
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_duty_notification_settings_singleton"),
        CheckConstraint("selected_method IN ('cron','n8n')", name="ck_duty_notification_settings_method"),
    )


class EmployeeExitInstructionShare(Base):
    """Одноразовая публичная копия текста инструкции по неугадываемому токену (см. TASKS №33)."""

    __tablename__ = "employee_exit_instruction_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Полный URL страницы (как в QR), чтобы совпадал с тем, что открывает телефон.
    public_view_url: Mapped[str] = mapped_column(String(768), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
