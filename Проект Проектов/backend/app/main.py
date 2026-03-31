from __future__ import annotations

import os
import random
import re
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from openpyxl import Workbook

try:
    from passlib.context import CryptContext
except Exception:  # pragma: no cover
    CryptContext = None  # type: ignore


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    DATABASE_PATH: str = "data/app.sqlite"
    EXPORTS_DIR: str = "exports"
    SESSION_SECRET: str = ""

    BOOTSTRAP_ADMIN_USERNAME: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    BOOTSTRAP_ADMIN_FULLNAME: str = ""

    PORT: int = 8000
    CORS_ALLOW_ORIGINS: str = ""  # comma-separated


settings = Settings()


def _pwd_context() -> "CryptContext":
    if CryptContext is None:
        raise RuntimeError("passlib is required for password hashing")
    return CryptContext(schemes=["bcrypt"], deprecated="auto")


pwd_context = _pwd_context()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # "admin" | "support"
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)

    duty_assignments: Mapped[list["DutyAssignment"]] = relationship(
        back_populates="support_user", cascade="all,delete"
    )
    reports: Mapped[list["DailyReport"]] = relationship(back_populates="support_user", cascade="all,delete")


class DutyAssignment(Base):
    __tablename__ = "duty_assignments"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    support_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        CheckConstraint("slot >= 0 AND slot <= 8", name="ck_duty_slot_range"),
    )

    support_user: Mapped[User] = relationship(back_populates="duty_assignments")


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    support_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    support_user: Mapped[User] = relationship(back_populates="reports")
    entries: Mapped[list["ReportEntry"]] = relationship(
        back_populates="report", cascade="all,delete-orphan", order_by="ReportEntry.id"
    )

    __table_args__ = (  # type: ignore[assignment]
        # Only one report per support user per date.
        UniqueConstraint("date", "support_user_id", name="uq_daily_report_date_employee"),
        CheckConstraint("status IN ('draft','final')", name="ck_daily_report_status"),
    )


class ReportEntry(Base):
    __tablename__ = "report_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("daily_reports.id"), nullable=False, index=True)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)

    report: Mapped[DailyReport] = relationship(back_populates="entries")


engine = None
SessionLocal = None  # type: ignore


def get_engine():
    global engine, SessionLocal
    if engine is not None:
        return engine

    db_path = Path(settings.DATABASE_PATH).expanduser()
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # sqlite URL; sqlite will create the file automatically
    url = f"sqlite:///{str(db_path)}"
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine


def init_db() -> None:
    eng = get_engine()
    Base.metadata.create_all(bind=eng)


@contextmanager
def db_session() -> Generator:
    if SessionLocal is None:
        get_engine()
    db = SessionLocal()  # type: ignore[misc]
    try:
        yield db
    finally:
        db.close()


def get_db():
    with db_session() as db:
        yield db


SLOT_START_HOUR = 9


def slot_start_time_str(slot: int) -> str:
    return (time(hour=SLOT_START_HOUR + slot, minute=0)).strftime("%H:%M")


def slot_time_delta(slot: int) -> timedelta:
    return timedelta(hours=slot)


def ensure_support_user(db, user_id: int) -> User:
    u = db.get(User, user_id)
    if not u or u.role != "support":
        raise HTTPException(status_code=400, detail="User is not a support user")
    return u


def get_current_user(request: Request, db=Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = db.get(User, int(user_id))
    if not user:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


def require_support_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("support", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class CreateSupportUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class AdminChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str


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
    slot: int = Field(ge=0, le=8)
    user_id: int = Field(ge=1)


class DutiesBatchRequest(BaseModel):
    date: date
    assignments: list[DutiesBatchSlot]


class ReportEntryIn(BaseModel):
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


EXPORT_FILENAME_RE = re.compile(r"^report_(\d+)_\d{4}-\d{2}-\d{2}\.xlsx$")


def exports_dir() -> Path:
    p = Path(settings.EXPORTS_DIR).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def report_excel_filename(report: DailyReport) -> str:
    return f"report_{report.id}_{report.date.isoformat()}.xlsx"


def build_report_excel(report: DailyReport, user: User) -> Path:
    out_dir = exports_dir()
    filename = report_excel_filename(report)
    out_path = out_dir / filename

    wb = Workbook()
    ws = wb.active
    ws.title = "Daily Report"

    # Header
    ws["A1"] = "Support Daily Report"
    ws["A3"] = "Employee"
    ws["B3"] = f"{user.full_name} ({user.username})"
    ws["A4"] = "Date"
    ws["B4"] = report.date.isoformat()
    ws["A5"] = "Status"
    ws["B5"] = report.status
    ws["A6"] = "GeneratedAt"
    ws["B6"] = datetime.utcnow().isoformat() + "Z"

    # Entries table
    ws["A8"] = "№"
    ws["B8"] = "Minutes"
    ws["C8"] = "Description"

    total_minutes = 0
    row = 9
    for idx, entry in enumerate(report.entries, start=1):
        ws[f"A{row}"] = idx
        ws[f"B{row}"] = entry.minutes
        ws[f"C{row}"] = entry.description
        total_minutes += entry.minutes
        row += 1

    ws[f"A{row + 1}"] = "TotalMinutes"
    ws[f"B{row + 1}"] = total_minutes

    # Basic column widths
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 80

    wb.save(out_path)
    return out_path


def report_to_out(db, report: DailyReport) -> DailyReportOut:
    employee = db.get(User, report.support_user_id)
    if not employee:
        raise HTTPException(status_code=500, detail="Employee not found")
    return DailyReportOut(
        report_id=report.id,
        date=report.date,
        employee_id=report.support_user_id,
        employee=UserOut(
            id=employee.id,
            username=employee.username,
            full_name=employee.full_name,
            role=employee.role,
        ),
        status=report.status,
        finalized_at=report.finalized_at,
        entries=[ReportEntryOut(minutes=e.minutes, description=e.description) for e in report.entries],
    )


app = FastAPI(title="Support Duty & Reports API")

cors_origins = [o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def bootstrap_admin_if_needed(db) -> None:
    existing_users_count = db.execute(select(func.count()).select_from(User)).scalar_one()
    if existing_users_count and existing_users_count > 0:
        return

    if not settings.BOOTSTRAP_ADMIN_USERNAME or not settings.BOOTSTRAP_ADMIN_PASSWORD or not settings.BOOTSTRAP_ADMIN_FULLNAME:
        raise RuntimeError("Bootstrap admin env vars are required: BOOTSTRAP_ADMIN_USERNAME/PASSWORD/FULLNAME")

    admin = User(
        username=settings.BOOTSTRAP_ADMIN_USERNAME,
        full_name=settings.BOOTSTRAP_ADMIN_FULLNAME,
        role="admin",
        password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
    )
    db.add(admin)
    db.commit()


@app.on_event("startup")
def on_startup() -> None:
    # init DB tables + bootstrap admin user
    init_db()
    if not settings.SESSION_SECRET:
        # SessionMiddleware needs it; use explicit error to avoid confusing auth failures.
        raise RuntimeError("SESSION_SECRET env var is required")

    with db_session() as db:
        bootstrap_admin_if_needed(db)


app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET, session_cookie="session")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/login", response_model=UserMeOut)
def login(payload: LoginRequest, request: Request, db=Depends(get_db)) -> UserMeOut:
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    request.session["user_id"] = str(user.id)
    return UserMeOut(id=user.id, username=user.username, full_name=user.full_name, role=user.role)


@app.post("/api/logout", response_model=LogoutOut)
def logout(request: Request) -> LogoutOut:
    request.session.clear()
    return LogoutOut(ok=True)


@app.get("/api/me", response_model=UserMeOut)
def me(current_user: User = Depends(get_current_user)) -> UserMeOut:
    return UserMeOut(id=current_user.id, username=current_user.username, full_name=current_user.full_name, role=current_user.role)


@app.get("/api/admin/users")
def admin_list_users(current_user: User = Depends(require_admin), db=Depends(get_db)) -> list[UserOut]:
    users = db.execute(select(User).where(User.role == "support").order_by(User.id)).scalars().all()
    return [
        UserOut(id=u.id, username=u.username, full_name=u.full_name, role=u.role)
        for u in users
    ]


@app.post("/api/admin/users", response_model=UserOut)
def admin_create_user(payload: CreateSupportUserRequest, current_user: User = Depends(require_admin), db=Depends(get_db)) -> UserOut:
    user = User(username=payload.username, full_name=payload.full_name, role="support", password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return UserOut(id=user.id, username=user.username, full_name=user.full_name, role=user.role)


@app.post("/api/admin/users/{user_id}/password")
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


@app.delete("/api/admin/users/{user_id}/reports")
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


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, current_user: User = Depends(require_admin), db=Depends(get_db)) -> dict:
    user = ensure_support_user(db, user_id)
    deleted_user_id = user.id
    db.delete(user)
    db.commit()
    return {"ok": True, "deleted_user_id": deleted_user_id}


@app.get("/api/duties", response_model=DutiesOut)
def get_duties(
    date_: date = Query(..., alias="date"),
    db=Depends(get_db),
    current_user: User = Depends(require_support_or_admin),
) -> DutiesOut:
    assignments = db.execute(
        select(DutyAssignment, User)
        .join(User, DutyAssignment.support_user_id == User.id)
        .where(DutyAssignment.date == date_)
    ).all()
    by_slot: dict[int, User] = {slot: user for (assignment, user) in assignments for slot in [assignment.slot]}

    slots_out: list[DutySlotOut] = []
    for slot in range(0, 9):
        user = by_slot.get(slot)
        slots_out.append(
            DutySlotOut(
                slot=slot,
                start_time=slot_start_time_str(slot),
                user=UserOut(id=user.id, username=user.username, full_name=user.full_name, role=user.role) if user else None,
            )
        )
    return DutiesOut(date=date_, slots=slots_out)


@app.post("/api/duties/generate", response_model=DutiesGenerateOut)
def generate_duties(payload: DutiesGenerateRequest, current_user: User = Depends(require_admin), db=Depends(get_db)) -> DutiesGenerateOut:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    support_users = db.execute(select(User).where(User.role == "support").order_by(User.id)).scalars().all()
    if not support_users:
        raise HTTPException(status_code=400, detail="No support users configured")

    user_ids = [u.id for u in support_users]

    # Prefetch existing assignments in the range
    existing_in_range: dict[tuple[date, int], int] = {}
    existing_rows = db.execute(
        select(DutyAssignment).where(DutyAssignment.date >= payload.start_date, DutyAssignment.date <= payload.end_date)
    ).scalars().all()
    for row in existing_rows:
        existing_in_range[(row.date, row.slot)] = row.support_user_id

    # counts prior to start_date
    counts = {
        uid: 0
        for uid in user_ids
    }
    grouped = db.execute(
        select(DutyAssignment.support_user_id, func.count())
        .where(DutyAssignment.date < payload.start_date)
        .group_by(DutyAssignment.support_user_id)
    ).all()
    for uid, cnt in grouped:
        if uid in counts:
            counts[uid] = int(cnt)

    created = 0
    rng = random.SystemRandom()

    with db_session() as tx_db:
        if payload.overwrite:
            tx_db.execute(
                delete(DutyAssignment).where(
                    DutyAssignment.date >= payload.start_date,
                    DutyAssignment.date <= payload.end_date,
                )
            )
            tx_db.commit()

        # Recompute counts inside transaction to be consistent with any changes made above
        for uid in user_ids:
            counts[uid] = int(
                tx_db.execute(
                    select(func.count())
                    .select_from(DutyAssignment)
                    .where(DutyAssignment.support_user_id == uid, DutyAssignment.date < payload.start_date)
                ).scalar_one()
            )

        for day_index in range((payload.end_date - payload.start_date).days + 1):
            current_day = payload.start_date + timedelta(days=day_index)
            for slot in range(0, 9):
                key = (current_day, slot)
                if (not payload.overwrite) and key in existing_in_range:
                    chosen_uid = existing_in_range[key]
                    counts[chosen_uid] = counts.get(chosen_uid, 0) + 1
                    continue

                min_count = min(counts.values())
                candidates = [uid for uid, c in counts.items() if c == min_count]
                chosen_uid = rng.choice(candidates)

                tx_db.add(DutyAssignment(date=current_day, slot=slot, support_user_id=chosen_uid))
                counts[chosen_uid] = counts.get(chosen_uid, 0) + 1
                created += 1

        tx_db.commit()

    return DutiesGenerateOut(
        start_date=payload.start_date,
        end_date=payload.end_date,
        overwrite=payload.overwrite,
        created_assignments=created,
    )


@app.post("/api/duties/batch")
def duties_batch(payload: DutiesBatchRequest, current_user: User = Depends(require_admin), db=Depends(get_db)) -> dict:
    if not payload.assignments:
        raise HTTPException(status_code=400, detail="assignments must not be empty")

    slots_seen: set[int] = set()
    for a in payload.assignments:
        if a.slot in slots_seen:
            raise HTTPException(status_code=400, detail="Duplicate slot in assignments")
        slots_seen.add(a.slot)

    # validate users
    user_ids = [a.user_id for a in payload.assignments]
    support_users = db.execute(select(User).where(User.id.in_(user_ids), User.role == "support")).scalars().all()
    support_user_ids = {u.id for u in support_users}
    missing = [uid for uid in user_ids if uid not in support_user_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"Some users are invalid: {missing[0]}")

    created = 0
    updated = 0
    with db_session() as tx_db:
        for a in payload.assignments:
            existing = tx_db.execute(
                select(DutyAssignment).where(DutyAssignment.date == payload.date, DutyAssignment.slot == a.slot)
            ).scalar_one_or_none()
            if existing:
                existing.support_user_id = a.user_id
                updated += 1
            else:
                tx_db.add(DutyAssignment(date=payload.date, slot=a.slot, support_user_id=a.user_id))
                created += 1
        tx_db.commit()

    return {"date": payload.date, "created": created, "updated": updated}


@app.post("/api/reports", response_model=DailyReportOut)
def create_or_get_report(payload: CreateOrGetReportRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)) -> DailyReportOut:
    target_support_id: int
    if current_user.role == "support":
        target_support_id = current_user.id
        if payload.employee_id is not None and payload.employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Cannot create report for other employee")
    else:
        # admin
        if payload.employee_id is None:
            target_support_id = current_user.id
        else:
            target_support_id = payload.employee_id

    employee = ensure_support_user(db, target_support_id)

    existing = db.execute(
        select(DailyReport).where(DailyReport.date == payload.date, DailyReport.support_user_id == employee.id)
    ).scalar_one_or_none()

    if existing:
        # Ensure entries loaded for output
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


@app.get("/api/reports", response_model=list[DailyReportOut])
def list_reports(
    date_: date = Query(..., alias="date"),
    employee_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> list[DailyReportOut]:
    # role restrictions
    if current_user.role == "support":
        if employee_id is not None and employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        employee_id = current_user.id
    else:
        # admin: if employee_id omitted -> all for that date
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


@app.put("/api/reports/{report_id}", response_model=DailyReportOut)
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

    if report.status == "final":
        raise HTTPException(status_code=409, detail="Report is finalized")

    new_date = payload.date or report.date
    new_support_id = payload.employee_id or report.support_user_id

    if current_user.role == "admin":
        if payload.employee_id is not None:
            ensure_support_user(db, payload.employee_id)
    else:
        # support can only update their own; ignore any provided fields
        new_date = report.date
        new_support_id = report.support_user_id

    # uniqueness check if admin changes date/support_user_id
    if (new_date != report.date) or (new_support_id != report.support_user_id):
        existing = db.execute(
            select(DailyReport).where(DailyReport.date == new_date, DailyReport.support_user_id == new_support_id, DailyReport.id != report.id)
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Report for this employee/date already exists")

    # Update fields + replace entries
    report.date = new_date
    report.support_user_id = new_support_id

    db.execute(delete(ReportEntry).where(ReportEntry.report_id == report.id))
    for entry in payload.entries:
        db.add(ReportEntry(report_id=report.id, minutes=entry.minutes, description=entry.description))

    db.commit()
    db.refresh(report)
    return report_to_out(db, report)


def _filename_safe(filename: str) -> bool:
    if not filename or "/" in filename or "\\" in filename:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", filename))


@app.post("/api/reports/{report_id}/finalize", response_model=ReportFinalizeOut)
def finalize_report(report_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)) -> ReportFinalizeOut:
    report = db.get(DailyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if current_user.role == "support" and report.support_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # If already finalized, just return existing URL.
    if report.status == "final":
        filename = report_excel_filename(report)
        return ReportFinalizeOut(report_id=report.id, status="final", excel_url=f"/exports/{filename}")

    employee = db.get(User, report.support_user_id)
    if not employee:
        raise HTTPException(status_code=500, detail="Employee not found")

    # Generate excel first, then mark finalized (so a failure won't mark it final).
    build_report_excel(report, employee)

    report.status = "final"
    report.finalized_at = datetime.utcnow()
    db.commit()
    db.refresh(report)

    filename = report_excel_filename(report)
    return ReportFinalizeOut(report_id=report.id, status="final", excel_url=f"/exports/{filename}")


@app.get("/exports/{filename}")
def download_export(filename: str, db=Depends(get_db)) -> FileResponse:
    # Path traversal protection + strict naming rule.
    if not _filename_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    m = EXPORT_FILENAME_RE.match(filename)
    if not m:
        raise HTTPException(status_code=404, detail="Not found")

    report_id = int(m.group(1))
    report = db.get(DailyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Not found")

    if report.status != "final":
        raise HTTPException(status_code=404, detail="Not finalized")

    out_path = (exports_dir() / filename).resolve()
    root = exports_dir().resolve()
    try:
        if not out_path.is_relative_to(root):  # py>=3.9
            raise HTTPException(status_code=400, detail="Invalid path")
    except AttributeError:  # pragma: no cover
        if str(root) not in str(out_path):
            raise HTTPException(status_code=400, detail="Invalid path")

    if not out_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=str(out_path), filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

