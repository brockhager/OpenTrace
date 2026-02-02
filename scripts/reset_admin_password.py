#!/usr/bin/env python3
"""
Reset an admin user's password.
Usage: python scripts/reset_admin_password.py [email]
If email is omitted, you will be prompted for it.
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db.session import async_session
from auth.models import AdminUser
from auth.security import get_password_hash


async def reset_password(email: str = None):
    if not email:
        email = input("Admin email: ").strip()
    if not email:
        print("Email is required")
        return

    import getpass
    pw = getpass.getpass("New password (min 8 chars): ").strip()
    confirm = getpass.getpass("Confirm password: ").strip()
    if pw != confirm:
        print("Passwords do not match")
        return
    if len(pw) < 8:
        print("Password must be at least 8 characters")
        return

    hashed = get_password_hash(pw)
    try:
        async with async_session() as db:
            result = await db.execute(AdminUser.__table__.select().where(AdminUser.email == email))
            user = result.scalar_one_or_none()
            if not user:
                print(f"Admin user not found: {email}")
                return
            user.hashed_password = hashed
            await db.commit()
        print(f"✅ Password updated for {email}")
    except Exception as e:
        print(f"Failed to reset password: {e}")


if __name__ == '__main__':
    email = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(reset_password(email))
