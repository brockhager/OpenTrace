# api/public.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import Optional, List
from pydantic import BaseModel
import re

from db.session import get_db_session
from api.models import PersonProfile
from auth.rate_limit import check_rate_limit
from auth.ip_log import IPLookupLog
from auth.deps import RateLimiter
from core.logger import logger

router = APIRouter(prefix="", tags=["public"])

class PersonProfilePublic(BaseModel):
    pfif_id: str
    given_name: Optional[str]
    family_name: Optional[str]
    age: Optional[int]
    sex: Optional[str]
    last_seen_location: Optional[str]
    status: str
    source: str
    profile_url: Optional[str]

    class Config:
        from_attributes = True

def sanitize_query(query: str) -> str:
    """Sanitize search query: strip SQL patterns, limit length."""
    if not query:
        return ""
    # Remove SQL-like patterns
    query = re.sub(r'[\'";\\]', '', query)
    # Remove excessive wildcards
    query = re.sub(r'%+', '%', query)
    # Limit length
    return query[:100].strip()

def is_suspicious_query(query: str) -> bool:
    """Check for suspicious patterns."""
    suspicious = ['union', 'select', 'drop', 'script', '<', '>', 'javascript', 'eval']
    return any(word in query.lower() for word in suspicious)

def validate_user_agent(user_agent: str) -> bool:
    """Basic bot detection."""
    if not user_agent:
        return False
    blocked = ['python-requests', 'scrapy', 'bot', 'crawler', 'spider']
    return not any(block.lower() in user_agent.lower() for block in blocked)

@router.get("/search")
async def search_profiles(
    q: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db_session),
    _ok: bool = Depends(RateLimiter("public_search", 20))
):
    """Public search for confirmed missing persons profiles."""
    ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "")

    # Bot mitigation
    if not validate_user_agent(user_agent):
        raise HTTPException(status_code=403, detail="Access denied")

    # Rate limiting: 20 searches/hour (injected dependency)
    # Use RateLimiter dependency via FastAPI's Depends mechanism
    # (ensures db and request are available and avoids db=None errors in tests)

    # Sanitize query
    if q:
        q = sanitize_query(q)
        if is_suspicious_query(q):
            # Log suspicious
            log_entry = IPLookupLog(
                ip_address=ip,
                action="suspicious_search",
                user_agent=user_agent,
                success=False
            )
            db.add(log_entry)
            await db.commit()
            raise HTTPException(status_code=400, detail="Invalid search query")

    # Build query
    query = select(PersonProfile).where(PersonProfile.is_confirmed == True)

    if q:
        # Fuzzy match on names
        query = query.where(
            or_(
                PersonProfile.given_name.ilike(f"%{q}%"),
                PersonProfile.family_name.ilike(f"%{q}%"),
                PersonProfile.alternate_names.any(q)
            )
        )

    if location:
        query = query.where(PersonProfile.last_seen_location.ilike(f"%{location}%"))

    if status:
        query = query.where(PersonProfile.status == status)

    if source:
        query = query.where(PersonProfile.author_name == source)

    # If DB is not configured (tests/local), return empty list
    if db is None:
        return []

    result = await db.execute(query)
    profiles = result.scalars().all()

    # Convert to public model
    public_profiles = []
    for p in profiles:
        source_name = p.author_name
        if "interpol" in p.pfif_id.lower():
            source_name = "Interpol via OpenSanctions"
        elif "charley" in p.pfif_id.lower():
            source_name = "Charley Project"
        elif "namus" in p.pfif_id.lower() or p.author_name == "NamUs":
            source_name = "NamUs"

        public_profiles.append(PersonProfilePublic(
            pfif_id=p.pfif_id,
            given_name=p.given_name,
            family_name=p.family_name,
            age=p.age,
            sex=p.sex,
            last_seen_location=p.last_seen_location,
            status=p.status,
            source=source_name,
            profile_url=p.profile_url
        ))

    # Log successful search
    log_entry = IPLookupLog(
        ip_address=ip,
        action="public_search",
        user_agent=user_agent,
        success=True
    )
    db.add(log_entry)
    await db.commit()

    logger.info("Public search performed", extra={
        "ip": ip,
        "user_agent": user_agent,
        "query": q,
        "location": location,
        "status": status,
        "source": source,
        "results_count": len(public_profiles),
        "action": "public_search"
    })

    return public_profiles

@router.get("/profile/{pfif_id}")
async def get_profile(pfif_id: str, request: Request = None, db: AsyncSession = Depends(get_db_session), _ok: bool = Depends(RateLimiter("profile_view", 50))):
    """Public view of a confirmed profile."""
    ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "")

    # Bot mitigation
    if not validate_user_agent(user_agent):
        raise HTTPException(status_code=403, detail="Access denied")

    # Rate limiting: 50 views/hour
    allowed = await check_rate_limit(db, ip, "profile_view", 50)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

    # Fetch profile
    result = await db.execute(select(PersonProfile).where(PersonProfile.pfif_id == pfif_id, PersonProfile.is_confirmed == True))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Determine source
    source_name = profile.author_name
    source_detail = ""
    if "interpol" in pfif_id.lower():
        source_name = "Interpol via OpenSanctions"
        source_detail = f"This record is sourced from Interpol Yellow Notices. Last updated: {profile.entry_date.date() if profile.entry_date else 'Unknown'}."
    elif "charley" in pfif_id.lower():
        source_name = "Charley Project"
        source_detail = f"This record is sourced from The Charley Project. Last updated: {profile.entry_date.date() if profile.entry_date else 'Unknown'}."
    elif "namus" in pfif_id.lower() or profile.author_name == "NamUs":
        source_name = "NamUs"
        source_detail = f"This record is sourced from NamUs (Case #{pfif_id.split('.')[-1]}). Last updated: {profile.entry_date.date() if profile.entry_date else 'Unknown'}."

    public_profile = PersonProfilePublic(
        pfif_id=profile.pfif_id,
        given_name=profile.given_name,
        family_name=profile.family_name,
        age=profile.age,
        sex=profile.sex,
        last_seen_location=profile.last_seen_location,
        status=profile.status,
        source=source_name,
        profile_url=profile.profile_url
    )

    # Log view
    log_entry = IPLookupLog(
        ip_address=ip,
        action="profile_view",
        user_agent=user_agent,
        success=True
    )
    db.add(log_entry)
    await db.commit()

    logger.info("Profile viewed", extra={
        "ip": ip,
        "user_agent": user_agent,
        "pfif_id": pfif_id,
        "action": "profile_view"
    })

    return {"profile": public_profile, "source_attribution": source_detail}