# api/admin.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel
from typing import Optional

from scrapers.opensanctions_client import OpenSanctionsClient
from scrapers.charley_scraper import CharleyScraper
from auth.ip_log import IPLookupLog
from auth.ban_list import IPBanList
from db.session import get_db_session
from auth.security import create_access_token, verify_password
from auth.models import AdminUser
from auth.deps import get_current_admin, require_admin_role
from core.logger import logger
from api.models import PersonProfile, IntelItem, ProfileLink, AuditLog

router = APIRouter(prefix="/admin", tags=["admin"])

class LoginRequest(BaseModel):
    email: str
    password: str

class ApproveProfileRequest(BaseModel):
    pfif_id: str
    confirm: bool = True
    justification: Optional[str] = None

@router.post("/login")
async def login(request: LoginRequest, req: Request, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(AdminUser).where(AdminUser.email == request.email, AdminUser.is_active == True))
    user = result.scalar_one_or_none()
    success = False
    if user and verify_password(request.password, user.hashed_password):
        access_token = create_access_token(data={"sub": user.email, "role": user.role})
        success = True
    else:
        access_token = None

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
        "email": request.email,
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
    stmt = update(PersonProfile).where(PersonProfile.pfif_id == request.pfif_id).values(is_confirmed=request.confirm)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Audit log
    audit = AuditLog(action="approve_profile", actor_id=str(user.id), target_id=request.pfif_id, details={"confirmed": request.confirm, "justification": request.justification})
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

@router.post("/scrape/namus", dependencies=[Depends(require_admin_role("admin"))])
async def trigger_namus_scrape(case_id: str):
    """Trigger manual NamUs scrape (for testing)."""
    # Mock - in real implementation, call scraper
    return {"message": f"Scrape triggered for NamUs case {case_id}"}

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