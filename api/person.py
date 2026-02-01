# api/person.py
"""
Person API endpoints for Opentrace
Provides public list/detail and admin CRUD for the Person entity.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from db.session import get_db_session
from models.person import Person
from auth.deps import require_admin_role, optional_admin
from auth.models import AdminUser

router = APIRouter(prefix="/api/persons", tags=["persons"])


class PersonCreateRequest(BaseModel):
    pfif_id: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    alternate_names: Optional[List[str]] = None
    age_at_disappearance: Optional[int] = None
    sex: Optional[str] = None
    status: Optional[str] = "missing"
    date_last_seen: Optional[datetime] = None
    date_reported: Optional[datetime] = None
    is_confirmed: Optional[bool] = False
    source_confidence: Optional[str] = "medium"
    primary_source: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    is_active: Optional[bool] = True
    data_sensitivity: Optional[str] = "standard"


class PersonUpdateRequest(BaseModel):
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    alternate_names: Optional[List[str]] = None
    age_at_disappearance: Optional[int] = None
    sex: Optional[str] = None
    status: Optional[str] = None
    date_last_seen: Optional[datetime] = None
    date_reported: Optional[datetime] = None
    is_confirmed: Optional[bool] = None
    source_confidence: Optional[str] = None
    primary_source: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    is_active: Optional[bool] = None
    data_sensitivity: Optional[str] = None


@router.get("")
async def list_persons(
    q: Optional[str] = Query(None, description="Name search query"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session)
):
    """List confirmed, active persons (public)."""
    if db is None:
        return {"persons": [], "total": 0}
    query = select(Person).where(Person.is_confirmed == True, Person.is_active == True)
    if q:
        query = query.where(
            (Person.given_name.ilike(f"%{q}%")) |
            (Person.family_name.ilike(f"%{q}%"))
        )
    result = await db.execute(query.limit(limit))
    persons = result.scalars().all()
    return {"persons": [p.to_public_dict() for p in persons], "total": len(persons)}


@router.get("/{pfif_id}")
async def get_person(
    pfif_id: str,
    db: AsyncSession = Depends(get_db_session),
    admin: Optional[AdminUser] = Depends(optional_admin)
):
    """Get a person by PFIF ID (public for confirmed, admin for unconfirmed)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    # If admin, show all persons (confirmed or not)
    if admin:
        result = await db.execute(
            select(Person).where(Person.pfif_id == pfif_id, Person.is_active == True)
        )
    else:
        # Public: only confirmed persons
        result = await db.execute(
            select(Person).where(Person.pfif_id == pfif_id, Person.is_confirmed == True, Person.is_active == True)
        )
    
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return {"person": person.to_public_dict()}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_person(
    request: PersonCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """Create a person (admin-only)."""
    person = Person(**request.model_dump())
    db.add(person)
    await db.commit()
    return {"pfif_id": person.pfif_id}


@router.patch("/{pfif_id}")
async def update_person(
    pfif_id: str,
    request: PersonUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """Update a person (admin-only)."""
    result = await db.execute(select(Person).where(Person.pfif_id == pfif_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    await db.commit()
    return {"message": "Person updated"}


@router.delete("/{pfif_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    pfif_id: str,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """Soft delete a person (admin-only)."""
    result = await db.execute(select(Person).where(Person.pfif_id == pfif_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    person.is_active = False
    await db.commit()
    return None
