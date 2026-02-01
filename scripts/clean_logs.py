"""
Auto-log expiry job for Opentrace.
Deletes records older than LOG_RETENTION_DAYS from ip_lookup_log and audit_log.
Designed to run as a daily cron job.
"""
import asyncio
import os
from sqlalchemy import text
from db.session import async_session
from core.logger import logger
from core.config import settings


async def clean_old_logs():
    """Delete logs older than LOG_RETENTION_DAYS."""
    logger.info("Starting log cleanup", extra={"action": "log_cleanup"})
    
    try:
        async with async_session() as db:
            # Clean ip_lookup_log
            result = await db.execute(
                text(f"DELETE FROM ip_lookup_log WHERE timestamp < NOW() - INTERVAL '{settings.LOG_RETENTION_DAYS} days'")
            )
            ip_logs_deleted = result.rowcount
            
            # Clean audit_log (optional - keep for compliance if needed)
            # Uncomment if you want to clean audit logs too
            # result = await db.execute(
            #     text(f"DELETE FROM audit_log WHERE timestamp < NOW() - INTERVAL '{settings.LOG_RETENTION_DAYS} days'")
            # )
            # audit_logs_deleted = result.rowcount
            
            await db.commit()
            
            logger.info("Log cleanup completed", extra={
                "ip_logs_deleted": ip_logs_deleted,
                "audit_logs_deleted": 0,  # Set to audit_logs_deleted if uncommented
                "retention_days": settings.LOG_RETENTION_DAYS,
                "action": "log_cleanup"
            })
            
    except Exception as e:
        logger.error("Log cleanup failed", extra={"error": str(e), "action": "log_cleanup"})
        raise


if __name__ == "__main__":
    asyncio.run(clean_old_logs())