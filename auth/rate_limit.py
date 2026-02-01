# auth/rate_limit.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, String
from sqlalchemy.ext.asyncio import AsyncSession
from auth.ip_log import IPLookupLog


async def check_rate_limit(db: AsyncSession | None, ip: str, action: str, max_per_hour: int) -> bool:
    """Check if IP has exceeded rate limit for action. Returns True if allowed.

    When `db` is None (e.g., in tests or local dev without DATABASE_URL),
    allow the request to prevent accidental 500s and make health endpoints usable.
    """
    if db is None:
        return True

    # Use naive UTC datetime to match column type (timestamp without timezone)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    # ip_address is stored as PostgreSQL INET; cast it to text for comparison to avoid operator errors
    result = await db.execute(
        select(func.count()).select_from(IPLookupLog)
        .where(func.cast(IPLookupLog.ip_address, String) == ip)
        .where(IPLookupLog.action == action)
        .where(IPLookupLog.timestamp > one_hour_ago)
        .where(IPLookupLog.success == True)
    )
    count = result.scalar() or 0
    return count < max_per_hour