# auth/rate_limit.py
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from auth.ip_log import IPLookupLog


async def check_rate_limit(db: AsyncSession, ip: str, action: str, max_per_hour: int) -> bool:
    """Check if IP has exceeded rate limit for action. Returns True if allowed."""
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    result = await db.execute(
        select(func.count()).select_from(IPLookupLog)
        .where(IPLookupLog.ip_address == ip)
        .where(IPLookupLog.action == action)
        .where(IPLookupLog.timestamp > one_hour_ago)
        .where(IPLookupLog.success == True)
    )
    count = result.scalar()
    return count < max_per_hour