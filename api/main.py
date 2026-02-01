from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from api.models import PersonProfile, IntelItem, ProfileLink, AuditLog
import os

app = FastAPI(title="Opentrace API", version="0.1.0")

# Security middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    from datetime import datetime
    from sqlalchemy import select
    from auth.ban_list import IPBanList
    from db.session import async_session

    client = request.client
    ip = client.host if client else "127.0.0.1"  # Default for tests

    async with async_session() as db:
        # Check IP ban
        result = await db.execute(
            select(IPBanList).where(IPBanList.ip_address == ip)
        )
        ban = result.scalar_one_or_none()
        if ban and (ban.expires_at is None or ban.expires_at > datetime.utcnow()):
            return JSONResponse(status_code=403, content={"detail": "IP banned"})

    response = await call_next(request)
    return response

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

class PDFSubmitRequest(BaseModel):
    pdf_url: str
    note: Optional[str] = ""

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
async def submit_intel(item: IntelItemRequest, req: Request, db: AsyncSession = Depends(get_db_session)):
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

    # Log submission
    log_entry = IPLookupLog(
        ip_address=req.client.host,
        action="/intel/submit",
        user_agent=req.headers.get("user-agent", ""),
        success=True
    )
    db.add(log_entry)
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

@app.post("/intel/submit-pdf")
async def submit_pdf(request: PDFSubmitRequest, req: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db_session)):
    """Submit public PDF URL for processing."""
    from scrapers.pdf_processor import PDFProcessor
    # Validate URL basic
    from urllib.parse import urlparse
    parsed = urlparse(request.pdf_url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="Only HTTPS URLs allowed")

    # Log submission attempt
    log_entry = IPLookupLog(
        ip_address=req.client.host,
        action="/intel/submit-pdf",
        user_agent=req.headers.get("user-agent", ""),
        success=True
    )
    db.add(log_entry)
    await db.commit()

    # Enqueue processing
    async def process():
        async with async_session() as db_inner:
            async with PDFProcessor() as processor:
                await processor.process_pdf(request.pdf_url, request.note, db_inner)

    background_tasks.add_task(process)
    return {"message": "PDF submission accepted for processing", "status": "processing"}

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

# Include public router
from api.public import router as public_router
app.include_router(public_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)