# api/admin.py
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from pydantic import BaseModel
from typing import Optional

from scrapers.opensanctions_client import OpenSanctionsClient
from scrapers.charley_scraper import CharleyScraper
from scrapers.generic_url_scraper import GenericUrlScraper
from auth.ip_log import IPLookupLog
from auth.ban_list import IPBanList
from db.session import get_db_session
from auth.security import create_access_token, verify_password
from auth.models import AdminUser
from auth.deps import get_current_admin, require_admin_role
from core.logger import logger
from api.models import PersonProfile, IntelItem, ProfileLink, AuditLog
from models.person import Person
from scrapers.namus_scraper import NamUsScraper
from db.session import async_session

router = APIRouter(prefix="/admin", tags=["admin"])

class LoginRequest(BaseModel):
    email: str
    password: str

class ApproveProfileRequest(BaseModel):
    pfif_id: str
    confirm: bool = True
    justification: Optional[str] = None

class ApprovePersonRequest(BaseModel):
    pfif_id: str
    confirm: bool = True
    justification: Optional[str] = None

class NamUsScrapeRequest(BaseModel):
    case_id: str

class NamUsScanRequest(BaseModel):
    start_case_id: str
    max_checks: int = 5

class UrlScrapeRequest(BaseModel):
    url: str


# Admin user management request shapes
class AdminCreateRequest(BaseModel):
    email: str
    password: str
    role: Optional[str] = "admin"

class AdminPasswordUpdateRequest(BaseModel):
    email: str
    password: str

class AdminActionRequest(BaseModel):
    email: str
    hard: Optional[bool] = False

@router.post("/login")
async def login(request: LoginRequest, req: Request, db: AsyncSession = Depends(get_db_session)):
    normalized_email = (request.email or "").strip().lower()
    result = await db.execute(
        select(AdminUser).where(
            func.lower(AdminUser.email) == normalized_email,
            AdminUser.is_active == True
        )
    )
    user = result.scalar_one_or_none()
    success = False
    pw_ok = False
    if user:
        try:
            pw_ok = verify_password(request.password, user.hashed_password)
        except Exception as e:
            logger.exception("Error verifying password", extra={"email": request.email})
            pw_ok = False
    if pw_ok:
        access_token = create_access_token(data={"sub": user.email, "role": user.role})
        success = True
    else:
        access_token = None

    # Log verification result for debugging (do not log password)
    logger.info("Admin login verification", extra={"email": normalized_email, "user_found": user is not None, "verify_ok": pw_ok, "success": success})

    # Log attempt
    log_entry = IPLookupLog(
        ip_address=req.client.host,
        action="login_attempt",
        user_agent=req.headers.get("user-agent", ""),
        success=success
    )
    db.add(log_entry)
    await db.commit()

    logger.info("Admin login attempt", extra={
        "ip": req.client.host if req.client else "unknown",
        "user_agent": req.headers.get("user-agent", ""),
        "email": normalized_email,
        "success": success,
        "action": "admin_login"
    })

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/review-queue", dependencies=[Depends(get_current_admin)])
async def get_review_queue(db: AsyncSession = Depends(get_db_session)):
    """List unreviewed intel items."""
    query = select(IntelItem).where(IntelItem.reviewed == False)
    result = await db.execute(query)
    queue = result.scalars().all()
    return {"queue": [i.__dict__ for i in queue]}

@router.get("/review-persons", dependencies=[Depends(require_admin_role("admin"))])
async def get_review_persons(db: AsyncSession = Depends(get_db_session)):
    """List unconfirmed persons from new Person table."""
    query = select(Person).where(Person.is_confirmed == False, Person.is_active == True)
    result = await db.execute(query)
    persons = result.scalars().all()
    return {"profiles": [person.to_admin_dict() for person in persons]}

@router.get("/all-persons", dependencies=[Depends(require_admin_role("admin"))])
async def get_all_persons(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session)
):
    """List ALL active persons (confirmed and unconfirmed) for admin management."""
    if db is None:
        return {"persons": [], "total": 0}
    query = select(Person).where(Person.is_active == True).limit(limit)
    result = await db.execute(query)
    persons = result.scalars().all()
    return {"persons": [p.to_admin_dict() for p in persons], "total": len(persons)}

@router.post("/approve-person", dependencies=[Depends(require_admin_role("admin"))])
async def approve_person(request: ApprovePersonRequest, user: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db_session)):
    """Approve or reject a person from new Person table."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    stmt = update(Person).where(Person.pfif_id == request.pfif_id).values(is_confirmed=request.confirm)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Audit log
    audit = AuditLog(
        action="approve_person",
        actor_id=str(user.id),
        target_id=None,
        details={
            "pfif_id": request.pfif_id,
            "confirmed": request.confirm,
            "justification": request.justification,
        },
    )
    db.add(audit)
    
    await db.commit()
    return {"message": f"Person {request.pfif_id} {'confirmed' if request.confirm else 'rejected'}"}

@router.get("/review-profiles", dependencies=[Depends(require_admin_role("admin"))])
async def get_review_profiles(db: AsyncSession = Depends(get_db_session)):
    """List unconfirmed profiles."""
    query = select(PersonProfile).where(PersonProfile.is_confirmed == False)
    result = await db.execute(query)
    profiles = result.scalars().all()
    return {"profiles": [p.__dict__ for p in profiles]}

@router.post("/approve-profile", dependencies=[Depends(require_admin_role("admin"))])
async def approve_profile(request: ApproveProfileRequest, user: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db_session)):
    """Approve or reject a profile."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    stmt = update(PersonProfile).where(PersonProfile.pfif_id == request.pfif_id).values(is_confirmed=request.confirm)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Audit log
    audit = AuditLog(
        action="approve_profile",
        actor_id=str(user.id),
        target_id=None,
        details={
            "pfif_id": request.pfif_id,
            "confirmed": request.confirm,
            "justification": request.justification,
        },
    )
    db.add(audit)
    
    await db.commit()
    return {"message": f"Profile {request.pfif_id} {'confirmed' if request.confirm else 'rejected'}"}

@router.post("/takedown", dependencies=[Depends(require_admin_role("admin"))])
async def takedown_profile(pfif_id: str, user: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db_session)):
    """Remove profile (GDPR compliance)."""
    # Delete profile (CASCADE will handle related records)
    stmt = delete(PersonProfile).where(PersonProfile.pfif_id == pfif_id)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Audit log
    audit = AuditLog(action="takedown", actor_id=str(user.id), target_id=None, details={"pfif_id": pfif_id})
    db.add(audit)
    
    await db.commit()
    return {"message": f"Profile {pfif_id} removed"}

def _normalize_namus_case_id(case_id: str) -> str:
    raw = case_id.strip()
    if raw.lower().startswith("mp"):
        return f"MP{raw[2:]}"
    if raw.isdigit():
        return f"MP{raw}"
    return raw

@router.post("/scrape/namus", dependencies=[Depends(require_admin_role("admin"))])
async def trigger_namus_scrape(request: NamUsScrapeRequest, db: AsyncSession = Depends(get_db_session)):
    """Trigger manual NamUs scrape for a single case ID."""
    case_id = _normalize_namus_case_id(request.case_id)
    async with NamUsScraper() as scraper:
        person_data = await scraper.scrape_case(case_id)
        if not person_data:
            return {"message": f"No public data found for NamUs case {case_id}", "found": False}

        if async_session is None or db is None:
            return {"message": f"Scrape completed for NamUs case {case_id}", "found": True, "person": person_data}

        created = await scraper.save_person(person_data)
        return {
            "message": f"Scrape completed for NamUs case {case_id}",
            "found": True,
            "created": created,
            "person": person_data
        }


# -------------------------------
# Admin user management endpoints
# -------------------------------

@router.get("/admins", dependencies=[Depends(require_admin_role("admin"))])
async def list_admins(db: AsyncSession = Depends(get_db_session)):
    """List admin users."""
    if db is None:
        return {"admins": [], "total": 0}
    result = await db.execute(select(AdminUser).order_by(AdminUser.email))
    rows = result.scalars().all()
    return {
        "admins": [
            {
                "id": str(r.id),
                "email": r.email,
                "role": r.role,
                "is_active": bool(r.is_active),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": len(rows)
    }

@router.post("/admins", dependencies=[Depends(require_admin_role("admin"))])
async def create_admin(request: AdminCreateRequest, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db_session)):
    """Create a new admin user."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    # Check exists
    result = await db.execute(select(AdminUser).where(AdminUser.email == request.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Admin user already exists")

    from auth.security import get_password_hash
    hashed = get_password_hash(request.password)
    new_user = AdminUser(email=request.email, hashed_password=hashed, role=request.role, is_active=True)
    db.add(new_user)

    audit = AuditLog(action="create_admin", actor_id=str(admin.id), target_id=None, details={"email": request.email})
    db.add(audit)

    await db.commit()
    return {"message": "admin_created", "email": request.email}


@router.post("/setup")
async def setup_admin(request: AdminCreateRequest, db: AsyncSession = Depends(get_db_session)):
    """Bootstrap the first admin account. Allowed only when no admin exists.

    This is a one-time convenience endpoint to create an initial admin on a fresh installation.
    It returns 403 if any admin account already exists.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    # Check whether any admin exists
    result = await db.execute(select(AdminUser).limit(1))
    any_admin = result.scalar_one_or_none()
    if any_admin:
        raise HTTPException(status_code=403, detail="Admin setup not allowed: admin user already exists")

    from auth.security import get_password_hash
    hashed = get_password_hash(request.password)
    new_user = AdminUser(email=request.email.strip().lower(), hashed_password=hashed, role=request.role or 'admin', is_active=True)
    db.add(new_user)

    audit = AuditLog(action="setup_admin", actor_id="system", target_id=None, details={"email": request.email})
    db.add(audit)

    await db.commit()
    return {"message": "admin_created", "email": request.email}


@router.get('/exists')
async def admin_exists(db: AsyncSession = Depends(get_db_session)):
    """Return whether an admin user exists (used by UI to detect first-run)."""
    if db is None:
        return {"admin_exists": False}
    result = await db.execute(select(AdminUser).limit(1))
    any_user = result.scalar_one_or_none()
    return {"admin_exists": bool(any_user)}


@router.get('/unconfirmed-count', dependencies=[Depends(get_current_admin)])
async def unconfirmed_count(db: AsyncSession = Depends(get_db_session)):
    """Return the total number of unconfirmed items across Person and PersonProfile.

    Intended for the admin UI badge to quickly show new items awaiting review.
    """
    if db is None:
        return {"count": 0}

    # Count unconfirmed persons (new Person table)
    p_stmt = select(func.count()).select_from(Person).where(Person.is_confirmed == False, Person.is_active == True)
    p_res = await db.execute(p_stmt)
    persons_count = int(p_res.scalar() or 0)

    # Count unconfirmed legacy profiles
    pp_stmt = select(func.count()).select_from(PersonProfile).where(PersonProfile.is_confirmed == False)
    pp_res = await db.execute(pp_stmt)
    profiles_count = int(pp_res.scalar() or 0)

    total = persons_count + profiles_count
    return {"count": total}

@router.post("/admins/password", dependencies=[Depends(require_admin_role("admin"))])
async def reset_admin_password(request: AdminPasswordUpdateRequest, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db_session)):
    """Reset an admin user's password."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = await db.execute(select(AdminUser).where(AdminUser.email == request.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")
    from auth.security import get_password_hash
    user.hashed_password = get_password_hash(request.password)

    audit = AuditLog(action="reset_admin_password", actor_id=str(admin.id), target_id=str(user.id), details={"email": user.email})
    db.add(audit)

    await db.commit()
    return {"message": "password_reset", "email": user.email}

@router.post("/admins/delete", dependencies=[Depends(require_admin_role("admin"))])
async def delete_admin(request: AdminActionRequest, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db_session)):
    """Deactivate (soft) or hard-delete an admin user."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    if request.hard:
        # Hard delete
        result = await db.execute(select(AdminUser).where(AdminUser.email == request.email))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Admin user not found")
        await db.execute(delete(AdminUser).where(AdminUser.email == request.email))
        action = "hard_delete_admin"
    else:
        await db.execute(update(AdminUser).where(AdminUser.email == request.email).values(is_active=False))
        action = "deactivate_admin"

    audit = AuditLog(action=action, actor_id=str(admin.id), target_id=None, details={"email": request.email, "hard": bool(request.hard)})
    db.add(audit)

    await db.commit()
    return {"message": action, "email": request.email}


@router.post("/scrape/namus-until-found", dependencies=[Depends(require_admin_role("admin"))])
async def scan_namus_until_found(request: NamUsScanRequest, db: AsyncSession = Depends(get_db_session)):
    """Scan NamUs case IDs starting at the provided ID until a public record is found.

    This is bounded by max_checks to avoid long-running requests.
    """
    start_id = _normalize_namus_case_id(request.start_case_id)
    if not start_id.lower().startswith("mp") or not start_id[2:].isdigit():
        raise HTTPException(status_code=400, detail="start_case_id must be numeric or start with MP")

    max_checks = max(1, min(request.max_checks, 20))
    start_num = int(start_id[2:])

    async with NamUsScraper() as scraper:
        for offset in range(max_checks):
            case_num = start_num + offset
            case_id = f"MP{case_num}"
            person_data = await scraper.scrape_case(case_id)
            if not person_data:
                await asyncio.sleep(scraper.RATE_LIMIT_DELAY)
                continue

            if async_session is None or db is None:
                return {
                    "message": f"Found public record for NamUs case {case_id}",
                    "found": True,
                    "case_id": case_id,
                    "person": person_data
                }

            created = await scraper.save_person(person_data)
            return {
                "message": f"Found public record for NamUs case {case_id}",
                "found": True,
                "created": created,
                "case_id": case_id,
                "person": person_data
            }

    return {"message": "No public record found in scan window", "found": False}

@router.post("/scrape/url", dependencies=[Depends(require_admin_role("admin"))])
async def scrape_from_url(request: UrlScrapeRequest):
    """Scrape data from a given URL (currently supports NamUs case pages)."""
    url = request.url.strip()
    
    # Parse URL to determine source and extract case ID
    if "namus.nij.ojp.gov" in url or "namus.gov" in url:
        # Extract case ID from NamUs URL
        # Examples: https://www.namus.gov/MissingPersons/Case#/146858
        #          https://namus.nij.ojp.gov/case/MP146858
        import re
        
        # Try different patterns
        match = re.search(r'/Case#?/(\d+)', url, re.IGNORECASE)
        if not match:
            match = re.search(r'/case/MP?(\d+)', url, re.IGNORECASE)
        if not match:
            match = re.search(r'MP(\d+)', url)
        
        if not match:
            raise HTTPException(
                status_code=400,
                detail=f"Could not extract case ID from URL: {url}"
            )
        
        case_id = f"MP{match.group(1)}"
        
        # Use NamUs scraper
        async with NamUsScraper() as scraper:
            person_data = await scraper.scrape_case(case_id)
            
            if not person_data:
                return {
                    "message": f"No data found at {url}",
                    "found": False,
                    "url": url
                }
            
            # Save to database
            created = await scraper.save_person(person_data)
            
            return {
                "message": f"Successfully scraped NamUs case {case_id}",
                "found": True,
                "created": created,
                "url": url,
                "case_id": case_id,
                "person": person_data
            }
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported URL source. Currently only NamUs URLs are supported."
        )

@router.post("/scrape/generic-url", dependencies=[Depends(require_admin_role("admin"))])
async def scrape_generic_url(request: UrlScrapeRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Scrape data from any missing persons URL.
    Supports common missing persons websites (not just NamUs).
    Extracts Person, Event, and Location data using generic patterns.
    """
    url = request.url.strip()
    
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(
            status_code=400,
            detail="URL must start with http:// or https://"
        )
    
    try:
        async with GenericUrlScraper() as scraper:
            person_data = await scraper.scrape_and_save_url(url)
            
            if not person_data:
                return {
                    "message": f"No missing persons data found at {url}",
                    "found": False,
                    "url": url
                }
            
            created = person_data.pop('created', False)
            
            return {
                "message": f"Successfully scraped missing persons data from URL",
                "found": True,
                "created": created,
                "url": url,
                "person": person_data
            }
    
    except Exception as e:
        logger.error(f"Error scraping generic URL: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error scraping URL: {str(e)}"
        )

@router.post("/ingest/opensanctions", dependencies=[Depends(require_admin_role("admin"))])
async def ingest_opensanctions(batch_size: int = 10, db: AsyncSession = Depends(get_db_session)):
    """Manual OpenSanctions ingestion."""
    async with OpenSanctionsClient() as client:
        stats = await client.ingest_all(db, max_batches=batch_size)
        return {"message": f"OpenSanctions ingestion triggered", "stats": stats}

@router.post("/ingest/charley", dependencies=[Depends(require_admin_role("admin"))])
async def ingest_charley(max_pages: int = 10, db: AsyncSession = Depends(get_db_session)):
    """Manual Charley Project ingestion."""
    async with CharleyScraper() as scraper:
        stats = await scraper.ingest_pages(db, max_pages=max_pages)
        return {"message": f"Charley Project ingestion triggered", "stats": stats}

@router.get("/security/logs", dependencies=[Depends(require_admin_role("admin"))])
async def get_security_logs(limit: int = 100, db: AsyncSession = Depends(get_db_session)):
    """View recent IP activity."""
    from sqlalchemy import desc
    result = await db.execute(
        select(IPLookupLog).order_by(desc(IPLookupLog.timestamp)).limit(limit)
    )
    logs = result.scalars().all()
    return {"logs": [log.__dict__ for log in logs]}

@router.post("/security/ban-ip", dependencies=[Depends(require_admin_role("admin"))])
async def ban_ip(ip: str, reason: str, expires_at: Optional[str] = None, db: AsyncSession = Depends(get_db_session)):
    """Ban IP (admin-only)."""
    from datetime import datetime
    from auth.ban_list import IPBanList
    expires = None
    if expires_at:
        expires = datetime.fromisoformat(expires_at)
    ban = IPBanList(ip_address=ip, reason=reason, expires_at=expires)
    db.add(ban)
    await db.commit()
    return {"message": f"IP {ip} banned"}