#!/usr/bin/env python3
"""
Admin utility: list admin users and verify a candidate password for an email.
Usage:
  python scripts/check_admins.py --list
  python scripts/check_admins.py --verify admin@example.com  # prompts for password
"""
import asyncio
import argparse
from getpass import getpass
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db.session import async_session
from auth.models import AdminUser
from auth.security import verify_password
from sqlalchemy import select


async def list_admins():
    async with async_session() as db:
        res = await db.execute(select(AdminUser))
        rows = res.scalars().all()
        for u in rows:
            print(f"{u.email}  | active={bool(u.is_active)}  | created_at={u.created_at}")


async def verify(email: str, candidate: str):
    async with async_session() as db:
        res = await db.execute(select(AdminUser).where(AdminUser.email == email))
        user = res.scalar_one_or_none()
        if not user:
            print(f"User not found: {email}")
            return 2
        ok = verify_password(candidate, user.hashed_password)
        print(f"verify_password => {ok}")
        print(f"is_active => {bool(user.is_active)}")
        return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true', help='List admin users')
    parser.add_argument('--verify', metavar='EMAIL', help='Verify password for EMAIL (prompts for password)')
    args = parser.parse_args()

    if args.list:
        asyncio.run(list_admins())
        return

    if args.verify:
        pw = getpass("Password: ")
        code = asyncio.run(verify(args.verify, pw))
        sys.exit(code)

    parser.print_help()


if __name__ == '__main__':
    main()
