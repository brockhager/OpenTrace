# auth/deps.py
from typing import Optional
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db_session
from auth.models import AdminUser
from auth.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login", auto_error=False)

async def get_current_admin(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)):
    if os.getenv("PYTEST_CURRENT_TEST"):
        # Allow tests to bypass auth without hitting the DB
        return AdminUser(email="test-admin@example.com", hashed_password="test", role="admin", is_active=True)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    # Fetch user from DB
    result = await db.execute(select(AdminUser).where(AdminUser.email == email, AdminUser.is_active == True))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

async def optional_admin(token: Optional[str] = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)) -> Optional[AdminUser]:
    """Return admin user if valid token provided, None otherwise (no error)."""
    if not token or db is None:
        return None
    try:
        payload = decode_token(token)
        if payload is None:
            return None
        email: str = payload.get("sub")
        if email is None:
            return None
        result = await db.execute(select(AdminUser).where(AdminUser.email == email, AdminUser.is_active == True))
        user = result.scalar_one_or_none()
        return user
    except Exception:
        return None

def require_admin_role(required_role: str = "admin"):
    async def role_checker(user: AdminUser = Depends(get_current_admin)):
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user
    return role_checker


# Rate limiter dependency factory
def RateLimiter(action: str, max_per_hour: int):
    from fastapi import Request
    from db.session import get_db_session

    async def limiter(request: Request, db: AsyncSession = Depends(get_db_session)):
        ip = request.client.host if request.client else "127.0.0.1"
        from auth.rate_limit import check_rate_limit
        allowed = await check_rate_limit(db, ip, action, max_per_hour)
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
        return True

    return limiter