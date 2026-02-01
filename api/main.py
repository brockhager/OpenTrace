from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, text
from api.models import PersonProfile, IntelItem, ProfileLink, AuditLog
from models.person import Person
from models.location import Location, PersonLocation
import os
from contextlib import asynccontextmanager

# Setup structured logging
from core.logger import logger
from core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    logger.info("Starting Opentrace API", extra={"action": "startup"})
    
    # Validate configuration
    try:
        settings.validate()
        logger.info("Configuration validated successfully", extra={"action": "config_validation"})
    except ValueError as e:
        logger.error(f"Configuration error: {e}", extra={"error": str(e), "action": "config_validation"})
        raise SystemExit(1)
    
    # Test database connection
    try:
        from db.session import async_session
        async with async_session() as db:
            # Check critical tables exist
            tables = ["person_profile", "admin_user"]
            for table in tables:
                stmt = text(f"SELECT 1 FROM {table} LIMIT 1")
                result = await db.execute(stmt)
                if not result:
                    logger.warning(f"Table {table} may not exist or is empty", extra={"table": table})
            logger.info("Database connectivity verified", extra={"action": "db_check"})
    except Exception as e:
        logger.error("Database connection failed", extra={"error": str(e)})
        raise
    
    # Check if admin user exists
    try:
        from db.session import async_session
        from auth.models import AdminUser
        async with async_session() as db:
            result = await db.execute(select(AdminUser).limit(1))
            admin_exists = result.scalar_one_or_none() is not None
            if not admin_exists:
                logger.warning("No admin user found - create one via /admin/setup or manual insertion", extra={"action": "admin_check"})
    except Exception as e:
        logger.warning("Could not check admin user existence", extra={"error": str(e)})
    
    yield
    
    # Shutdown
    logger.info("Shutting down Opentrace API", extra={"action": "shutdown"})

app = FastAPI(title="Opentrace API", version="0.1.0", lifespan=lifespan)

# Security middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    from datetime import datetime
    from sqlalchemy import select, cast, String
    from auth.ban_list import IPBanList
    from db.session import async_session

    client = request.client
    ip = client.host if client else "127.0.0.1"  # Default for tests

    async with async_session() as db:
        # Check IP ban (compare as text to avoid inet vs varchar operator errors)
        result = await db.execute(
            select(IPBanList).where(cast(IPBanList.ip_address, String) == ip)
        )
        ban = result.scalar_one_or_none()
        if ban and (ban.expires_at is None or ban.expires_at > datetime.utcnow()):
            logger.warning("IP banned - request blocked", extra={
                "ip": ip,
                "user_agent": request.headers.get("user-agent", ""),
                "path": request.url.path,
                "action": "ip_ban_blocked"
            })
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
async def search_profiles(
    q: Optional[str] = None, 
    location: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: int = 50,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Search person profiles with location-aware capabilities.
    
    Parameters:
    - q: Name search query
    - location: Location name search
    - lat/lng: Coordinate search (overrides location)
    - radius_km: Search radius for coordinate search
    """
    
    # If coordinates provided, use spatial search via location API
    if lat is not None and lng is not None:
        # Import here to avoid circular imports
        from api.location import find_nearby_persons
        return await find_nearby_persons(lat, lng, radius_km, None, db)
    
    # Use new Person model for search
    query = select(Person).where(Person.is_confirmed == True, Person.is_active == True)
    
    # Location-based search (join with person_location)
    if location:
        query = query.join(PersonLocation).join(Location).where(
            Location.display_name.ilike(f"%{location}%") |
            Location.locality.ilike(f"%{location}%") |
            Location.admin1_name.ilike(f"%{location}%")
        )
    
    # Name search
    if q:
        query = query.where(
            (Person.given_name.ilike(f"%{q}%")) |
            (Person.family_name.ilike(f"%{q}%"))
        )
    
    result = await db.execute(query)
    profiles = result.scalars().all()
    
    # Return new API response shape
    return {"results": [person.to_public_dict() for person in profiles]}

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
async def get_sources(db: AsyncSession = Depends(get_db_session)):
    """
    List all active data sources with last update times.
    
    Phase 16: Now queries the Source entity for dynamic, up-to-date source registry.
    """
    try:
        from models.source import Source
        from sqlalchemy import select
        
        result = await db.execute(
            select(Source).where(Source.is_active == True).order_by(Source.source_name)
        )
        sources = result.scalars().all()
        
        return {
            "sources": [
                {
                    "source_id": str(source.source_id),
                    "name": source.source_name,
                    "code": source.source_code,
                    "type": source.source_type,
                    "category": source.source_category,
                    "trust_tier": source.trust_tier,
                    "last_update": source.last_successful_fetch.isoformat() if source.last_successful_fetch 
                                   else source.updated_at.isoformat() if source.updated_at 
                                   else source.created_at.isoformat() if source.created_at 
                                   else "2024-01-01T00:00:00Z",
                    "reliability_score": float(source.reliability_score) if source.reliability_score else None,
                    "is_active": source.is_active
                }
                for source in sources
            ],
            "total": len(sources)
        }
    except Exception as e:
        # Fallback to static response if database unavailable
        logger.error(f"Failed to query sources from database: {e}")
        return {
            "sources": [
                {"name": "NamUs", "last_update": "2024-01-01T00:00:00Z"},
                {"name": "Interpol Yellow Notices", "last_update": "2024-01-01T00:00:00Z"},
                {"name": "The Charley Project", "last_update": "2024-01-01T00:00:00Z"}
            ],
            "total": 3,
            "fallback": True
        }


@app.get("/favicon.ico")
async def favicon():
    """Return 404 for favicon requests (API-only app)."""
    raise HTTPException(status_code=404, detail="Not found")

# Include location router
from api.location import router as location_router
app.include_router(location_router)

# Include admin router
from api.admin import router as admin_router
app.include_router(admin_router)

# Include public router
from api.public import router as public_router
app.include_router(public_router)

# Include health router
from api.health import router as health_router
app.include_router(health_router)

# Include event router
from api.event import router as event_router
app.include_router(event_router)

# Include source router
from api.source import router as source_router
app.include_router(source_router)

# Include person router
from api.person import router as person_router
app.include_router(person_router)

# Serve frontend static files and index
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

@app.get("/admin.html")
async def admin_page():
    return FileResponse("frontend/admin.html")

@app.get("/profile.html")
async def profile_page():
    return FileResponse("frontend/profile.html")

@app.get("/persons.html")
async def persons_page():
    return FileResponse("frontend/persons.html")

@app.get("/locations.html")
async def locations_page():
    return FileResponse("frontend/locations.html")

@app.get("/events.html")
async def events_page():
    return FileResponse("frontend/events.html")

@app.get("/sources.html")
async def sources_page():
    return FileResponse("frontend/sources.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)