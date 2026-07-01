from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import UsefulResource, User
from app.schemas import UsefulResourceCategoriesUpdate, UsefulResourceOut
from app.useful_resources_seed import normalize_resource_categories

router = APIRouter()


def _resource_to_out(row: UsefulResource) -> UsefulResourceOut:
    cats = row.categories if isinstance(row.categories, list) else []
    return UsefulResourceOut(
        id=row.id,
        slug=row.slug,
        title=row.title,
        description=row.description or "",
        url=row.url,
        image=row.image_path or "",
        color=row.color or "#2563eb",
        categories=[str(c) for c in cats],
        sort_order=row.sort_order,
    )


@router.get("/api/useful-resources", response_model=list[UsefulResourceOut])
def list_useful_resources(
    _current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> list[UsefulResourceOut]:
    rows = db.scalars(select(UsefulResource).order_by(UsefulResource.sort_order, UsefulResource.id)).all()
    return [_resource_to_out(r) for r in rows]


@router.patch("/api/admin/useful-resources/{resource_id}", response_model=UsefulResourceOut)
def update_useful_resource_categories(
    resource_id: int,
    payload: UsefulResourceCategoriesUpdate,
    _admin: User = Depends(require_admin),
    db=Depends(get_db),
) -> UsefulResourceOut:
    row = db.get(UsefulResource, resource_id)
    if not row:
        raise HTTPException(status_code=404, detail="Resource not found")
    try:
        row.categories = normalize_resource_categories(payload.categories)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return _resource_to_out(row)
