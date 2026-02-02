#!/usr/bin/env python3
"""
Reset an admin user's password.
Usage: python scripts/reset_admin_password.py [email]
If email is omitted, you will be prompted for it.
"""
import sys
import asyncio
from pathlib import Path
import re
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db.session import async_session
from auth.models import AdminUser
from auth.security import get_password_hash


async def reset_password(email: str = None, no_check: bool = False):
    if not email:
        email = input("Admin email: ").strip()
    if not email:
        print("Email is required")
        return

    import getpass
    if not no_check:
        print("Password requirements: at least 8 characters, include uppercase and lowercase letters, a number, and a symbol.")
        pw = getpass.getpass("New password (min 8 chars, include upper/lowercase, number, symbol): ").strip()
        confirm = getpass.getpass("Confirm password: ").strip()
        if pw != confirm:
            print("Passwords do not match")
            return
        # Enforce complexity
        if len(pw) < 8 or not re.search(r"[A-Z]", pw) or not re.search(r"[a-z]", pw) or not re.search(r"[0-9]", pw) or not re.search(r"[^A-Za-z0-9]", pw):
            print("Password must be at least 8 characters and include uppercase, lowercase, a number, and a symbol")
            return
    else:
        pw = getpass.getpass("New password (no checks): ").strip()
        confirm = getpass.getpass("Confirm password: ").strip()
        if pw != confirm:
            print("Passwords do not match")
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
    parser = argparse.ArgumentParser(description='Reset an admin password')
    parser.add_argument('email', nargs='?', help='Admin email')
    parser.add_argument('--no-check', action='store_true', help='Skip password complexity checks')
    args = parser.parse_args()
    asyncio.run(reset_password(args.email, args.no_check))
