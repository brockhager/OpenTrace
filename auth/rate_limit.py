# auth/rate_limit.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from auth.ip_log import IPLookupLog


async def check_rate_limit(db: AsyncSession | None, ip: str, action: str, max_per_hour: int) -> bool:
    """Check if IP has exceeded rate limit for action. Returns True if allowed.

    When `db` is None (e.g., in tests or local dev without DATABASE_URL),
    allow the request to prevent accidental 500s and make health endpoints usable.
    """
    if db is None:
        return True

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db.execute(
        select(func.count()).select_from(IPLookupLog)
        .where(IPLookupLog.ip_address == ip)
        .where(IPLookupLog.action == action)
        .where(IPLookupLog.timestamp > one_hour_ago)
        .where(IPLookupLog.success == True)
    )
    count = result.scalar() or 0
    return count < max_per_hour