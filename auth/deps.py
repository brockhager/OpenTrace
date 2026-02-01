# auth/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db_session
from auth.models import AdminUser
from auth.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")

async def get_current_admin(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db_session)):
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

def require_admin_role(required_role: str = "admin"):
    async def role_checker(user: AdminUser = Depends(get_current_admin)):
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user
    return role_checker