# api/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from db.session import get_db_session
from api.models import PersonProfile, IntelItem
from auth.models import AdminUser
from auth.ban_list import IPBanList
from auth.ip_log import IPLookupLog
from core.logger import logger
import time

router = APIRouter(prefix="", tags=["health"])

# Track startup time for uptime calculation
START_TIME = time.time()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db_session)):
    """Health check endpoint for liveness/readiness probes."""
    health_status = {
        "status": "healthy",
        "database": True,
        "uptime_seconds": int(time.time() - START_TIME)
    }
    
    try:
        # Check database connectivity
        await db.execute(text("SELECT 1"))
        
        # Check critical tables exist and have data
        tables_checks = {
            "person_profile": PersonProfile,
            "admin_user": AdminUser
        }
        
        for table_name, model in tables_checks.items():
            result = await db.execute(select(model).limit(1))
            exists = result.scalar_one_or_none() is not None
            health_status[f"{table_name}_exists"] = exists
            
    except Exception as e:
        logger.error("Health check failed", extra={"error": str(e), "action": "health_check"})
        health_status["status"] = "unhealthy"
        health_status["database"] = False
        health_status["error"] = str(e)
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    logger.info("Health check performed", extra={
        "status": health_status["status"],
        "database": health_status["database"],
        "uptime_seconds": health_status["uptime_seconds"],
        "action": "health_check"
    })
    
    return health_status


@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db_session)):
    """Operational metrics endpoint for internal visibility."""
    try:
        # Search requests in last 24h
        result = await db.execute(
            text("""
                SELECT COUNT(*) FROM ip_lookup_log 
                WHERE action = 'public_search' 
                AND timestamp > NOW() - INTERVAL '24 hours'
            """)
        )
        search_requests_24h = result.scalar()
        
        # Banned IPs total
        result = await db.execute(select(func.count(IPBanList.id)))
        banned_ips_total = result.scalar()
        
        # Unreviewed intel count
        result = await db.execute(
            select(func.count(IntelItem.id)).where(IntelItem.reviewed == False)
        )
        unreviewed_intel_count = result.scalar()
        
        # PDF submissions in last 24h
        result = await db.execute(
            text("""
                SELECT COUNT(*) FROM ip_lookup_log 
                WHERE action = '/intel/submit-pdf' 
                AND timestamp > NOW() - INTERVAL '24 hours'
            """)
        )
        pdf_submissions_24h = result.scalar()
        
        metrics = {
            "search_requests_24h": search_requests_24h or 0,
            "banned_ips_total": banned_ips_total or 0,
            "unreviewed_intel_count": unreviewed_intel_count or 0,
            "pdf_submissions_24h": pdf_submissions_24h or 0
        }
        
        logger.info("Metrics requested", extra={
            "action": "metrics_request",
            **metrics
        })
        
        return metrics
        
    except Exception as e:
        logger.error("Metrics retrieval failed", extra={"error": str(e), "action": "metrics_error"})
        raise