from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from api.models import PersonProfile, IntelItem, ProfileLink, AuditLog
import os

app = FastAPI(title="Opentrace API", version="0.1.0")

# Database setup moved to db/session.py
from db.session import get_db_session

# Models
class IntelItemRequest(BaseModel):
    source_url: str
    text: Optional[str] = None
    category: Optional[str] = "sighting"
    confidence_rating: Optional[str] = "low"

class BulkIntelRequest(BaseModel):
    items: List[IntelItemRequest]

# Mock authentication (replace with real JWT/OAuth)
def get_current_user():
    # Placeholder - implement proper auth
    return {"role": "admin", "id": "mock_user"}

def require_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user

# Public endpoints
@app.get("/search")
async def search_profiles(q: str, location: Optional[str] = None, db: AsyncSession = Depends(get_db_session)):
    """Search person profiles (public or reviewed intel only)."""
    query = select(PersonProfile).where(PersonProfile.is_confirmed == True)
    if location:
        query = query.where(PersonProfile.last_seen_location.ilike(f"%{location}%"))
    # Simple text search on names
    if q:
        query = query.where(
            (PersonProfile.given_name.ilike(f"%{q}%")) |
            (PersonProfile.family_name.ilike(f"%{q}%")) |
            (PersonProfile.alternate_names.any(q))
        )
    result = await db.execute(query)
    profiles = result.scalars().all()
    return {"results": [p.__dict__ for p in profiles]}

@app.post("/intel/submit")
async def submit_intel(item: IntelItemRequest, db: AsyncSession = Depends(get_db_session)):
    """Submit community intel (requires source_url)."""
    if not item.source_url:
        raise HTTPException(status_code=400, detail="source_url required")

    # PII filtering
    if item.text and any(word in item.text.lower() for word in ["phone", "email", "address"]):
        raise HTTPException(status_code=400, detail="PII detected - remove sensitive info")

    # For now, assume person_pfif_id is derived or optional; in real impl, match to profile
    intel = IntelItem(
        person_pfif_id=None,  # Set to None or match logic
        author_name="anonymous",
        source_url=item.source_url,
        text=item.text,
        category=item.category,
        confidence_rating=item.confidence_rating
    )
    db.add(intel)
    await db.commit()
    return {"message": "Intel submitted for review"}

@app.post("/intel/bulk-submit")
async def bulk_submit_intel(request: BulkIntelRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    """Bulk submit intel for trusted partners."""
    for item in request.items:
        if not item.source_url:
            raise HTTPException(status_code=400, detail="All items must have source_url")

        # PII filtering
        if item.text and any(word in item.text.lower() for word in ["phone", "email", "address"]):
            raise HTTPException(status_code=400, detail="PII detected in bulk submission")

        intel = IntelItem(
            person_pfif_id=None,
            author_name=user["id"],
            source_url=item.source_url,
            text=item.text,
            category=item.category,
            confidence_rating=item.confidence_rating,
            reviewed=True  # Trusted partners get auto-review
        )
        db.add(intel)
    await db.commit()
    return {"message": f"Bulk submitted {len(request.items)} items"}

@app.get("/profiles/{profile_id}/intel")
async def get_profile_intel(profile_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get reviewed intel for a profile."""
    query = select(IntelItem).where(IntelItem.person_pfif_id == profile_id, IntelItem.reviewed == True)
    result = await db.execute(query)
    intel = result.scalars().all()
    return {"intel": [i.__dict__ for i in intel]}

@app.get("/sources")
async def get_sources():
    """List data sources with last update times."""
    return {
        "sources": [
            {"name": "NamUs", "last_update": "2024-01-01T00:00:00Z"},
            {"name": "Interpol Yellow Notices", "last_update": "2024-01-01T00:00:00Z"},
            {"name": "The Charley Project", "last_update": "2024-01-01T00:00:00Z"}
        ]
    }


# Include admin router
from api.admin import router as admin_router
app.include_router(admin_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)