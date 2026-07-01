from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select

from app.database import get_db
from app.deps import get_current_user
from app.duty_slots import slot_start_time_str
from app.models import DutySwapRequest, User
from app.schemas import RecentActivityItemOut

router = APIRouter()


def _swap_activity_item(row: DutySwapRequest, current_user: User, users: dict[int, User]) -> RecentActivityItemOut:
    incoming = row.target_user_id == current_user.id
    requester = users.get(row.requester_user_id)
    target = users.get(row.target_user_id)
    req_name = (requester.full_name or requester.username) if requester else "Сотрудник"
    tgt_name = (target.full_name or target.username) if target else "Сотрудник"
    slot_line = (
        f"{row.date.isoformat()}, {slot_start_time_str(row.from_slot)} → {slot_start_time_str(row.to_slot)}"
    )

    if incoming:
        if row.status == "pending":
            title = "Входящий обмен дежурствами"
            detail = row.message or f"{req_name} · {slot_line}"
        elif row.status == "accepted":
            title = "Обмен принят"
            detail = f"{req_name} · {slot_line}"
        else:
            title = "Обмен отклонён"
            detail = f"{req_name} · {slot_line}"
        kind = "swap_incoming"
    else:
        if row.status == "pending":
            title = "Исходящий обмен дежурствами"
            detail = f"Ожидает ответа {tgt_name} · {slot_line}"
        elif row.status == "accepted":
            title = "Ваш обмен принят"
            detail = f"{tgt_name} · {slot_line}"
        else:
            title = "Ваш обмен отклонён"
            detail = f"{tgt_name} · {slot_line}"
        kind = "swap_outgoing"

    return RecentActivityItemOut(
        id=f"swap-{row.id}",
        kind=kind,
        title=title,
        detail=detail,
        at=row.created_at,
        status=row.status,
    )


@router.get("/api/activity/recent", response_model=list[RecentActivityItemOut])
def list_recent_activity(
    limit: int = Query(8, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> list[RecentActivityItemOut]:
    if current_user.role not in ("support", "admin"):
        return []

    uid = int(current_user.id)
    rows = db.execute(
        select(DutySwapRequest)
        .where(
            or_(
                DutySwapRequest.requester_user_id == uid,
                DutySwapRequest.target_user_id == uid,
            )
        )
        .order_by(DutySwapRequest.created_at.desc())
        .limit(limit)
    ).scalars().all()

    user_ids = {uid}
    for row in rows:
        user_ids.add(int(row.requester_user_id))
        user_ids.add(int(row.target_user_id))
    users = {
        int(u.id): u
        for u in db.execute(select(User).where(User.id.in_(user_ids))).scalars().all()
    }

    return [_swap_activity_item(row, current_user, users) for row in rows]
