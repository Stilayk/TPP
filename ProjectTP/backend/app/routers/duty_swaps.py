from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.database import get_db
from app.deps import ensure_support_user, get_current_user
from app.duty_slots import slot_start_time_str
from app.models import DutyAssignment, DutySwapRequest, User
from app.schemas import DutySwapCreateRequest, DutySwapDecisionRequest, DutySwapOut

router = APIRouter()


@router.post("/api/duty-swaps", response_model=DutySwapOut)
def create_duty_swap_request(
    payload: DutySwapCreateRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> DutySwapOut:
    if current_user.role != "support":
        raise HTTPException(status_code=403, detail="Only support users can create swap requests")
    if not current_user.is_active_for_duties:
        raise HTTPException(
            status_code=403,
            detail="Duty swap is not available while participation in the duty schedule is disabled",
        )
    if payload.from_slot == payload.to_slot:
        raise HTTPException(status_code=400, detail="Choose different duty slots")

    requester_assignment = db.execute(
        select(DutyAssignment).where(
            DutyAssignment.date == payload.date,
            DutyAssignment.slot == payload.from_slot,
        )
    ).scalar_one_or_none()
    if not requester_assignment or requester_assignment.support_user_id != current_user.id:
        raise HTTPException(status_code=400, detail="You are not assigned to the selected source slot")

    target_assignment = db.execute(
        select(DutyAssignment).where(
            DutyAssignment.date == payload.date,
            DutyAssignment.slot == payload.to_slot,
        )
    ).scalar_one_or_none()
    if not target_assignment:
        raise HTTPException(status_code=400, detail="Target slot has no assigned employee")

    target_user = ensure_support_user(db, int(target_assignment.support_user_id))
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot create swap request with yourself")

    message = (
        f"{target_user.full_name}, {current_user.full_name} запрашивает обмен дежурствами "
        f"с {slot_start_time_str(payload.from_slot)} на {slot_start_time_str(payload.to_slot)}"
    )
    row = DutySwapRequest(
        date=payload.date,
        from_slot=payload.from_slot,
        to_slot=payload.to_slot,
        requester_user_id=current_user.id,
        target_user_id=target_user.id,
        message=message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return DutySwapOut(
        id=row.id,
        date=row.date,
        from_slot=row.from_slot,
        to_slot=row.to_slot,
        requester_user_id=row.requester_user_id,
        target_user_id=row.target_user_id,
        message=row.message,
        status=row.status,
        created_at=row.created_at,
    )


@router.get("/api/duty-swaps/inbox", response_model=list[DutySwapOut])
def list_duty_swap_inbox(
    date_: Optional[date] = Query(None, alias="date"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> list[DutySwapOut]:
    if current_user.role != "support":
        return []
    stmt = select(DutySwapRequest).where(DutySwapRequest.target_user_id == current_user.id)
    if date_ is not None:
        stmt = stmt.where(DutySwapRequest.date == date_)
    rows = db.execute(stmt.order_by(DutySwapRequest.created_at.desc())).scalars().all()
    return [
        DutySwapOut(
            id=r.id,
            date=r.date,
            from_slot=r.from_slot,
            to_slot=r.to_slot,
            requester_user_id=r.requester_user_id,
            target_user_id=r.target_user_id,
            message=r.message,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/api/duty-swaps/{swap_id}/decision", response_model=DutySwapOut)
def decide_duty_swap_request(
    swap_id: int,
    payload: DutySwapDecisionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> DutySwapOut:
    if current_user.role != "support":
        raise HTTPException(status_code=403, detail="Only support users can decide swap requests")

    row = db.get(DutySwapRequest, swap_id)
    if not row:
        raise HTTPException(status_code=404, detail="Swap request not found")
    if row.target_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Swap request is already processed")

    if payload.action == "accept":
        requester_slot = db.execute(
            select(DutyAssignment).where(
                DutyAssignment.date == row.date,
                DutyAssignment.slot == row.from_slot,
            )
        ).scalar_one_or_none()
        target_slot = db.execute(
            select(DutyAssignment).where(
                DutyAssignment.date == row.date,
                DutyAssignment.slot == row.to_slot,
            )
        ).scalar_one_or_none()
        if not requester_slot or not target_slot:
            raise HTTPException(status_code=409, detail="Duty slots are missing")
        if requester_slot.support_user_id != row.requester_user_id or target_slot.support_user_id != row.target_user_id:
            raise HTTPException(status_code=409, detail="Duty assignments changed, recreate swap request")

        requester_slot.support_user_id, target_slot.support_user_id = target_slot.support_user_id, requester_slot.support_user_id
        row.status = "accepted"
    else:
        row.status = "rejected"

    db.add(row)
    db.commit()
    db.refresh(row)
    return DutySwapOut(
        id=row.id,
        date=row.date,
        from_slot=row.from_slot,
        to_slot=row.to_slot,
        requester_user_id=row.requester_user_id,
        target_user_id=row.target_user_id,
        message=row.message,
        status=row.status,
        created_at=row.created_at,
    )
