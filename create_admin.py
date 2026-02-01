#!/usr/bin/env python3
"""
CLI script to create the first admin user for Opentrace.
Usage: python create_admin.py --email admin@example.com --password mypassword
"""
import asyncio
import argparse
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import async_session
from auth.models import AdminUser
from auth.security import get_password_hash

async def create_admin(email: str, password: str, role: str = "admin"):
    async with async_session() as session:
        # Check if user already exists
        from sqlalchemy import select
        result = await session.execute(select(AdminUser).where(AdminUser.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User with email {email} already exists.")
            return

        # Create new admin user
        hashed_password = get_password_hash(password)
        admin = AdminUser(email=email, hashed_password=hashed_password, role=role)
        session.add(admin)
        await session.commit()
        print(f"Admin user {email} created successfully with role {role}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an admin user for Opentrace.")
    parser.add_argument("--email", required=True, help="Email address for the admin user")
    parser.add_argument("--password", required=True, help="Password for the admin user")
    parser.add_argument("--role", default="admin", choices=["admin", "trusted_partner"], help="Role for the user")

    args = parser.parse_args()
    asyncio.run(create_admin(args.email, args.password, args.role))