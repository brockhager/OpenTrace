#!/usr/bin/env python3
"""
Database initialization script for OpenTrace.
This script creates all required tables in the PostgreSQL database.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import settings
from db.session import engine
from sqlalchemy import text


async def init_database():
    """Initialize the database with required schema."""
    print("🚀 Initializing OpenTrace database...")

    # Validate configuration
    try:
        settings.validate()
        print("✅ Configuration validated")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Read the schema file
    schema_path = project_root / "databases" / "db_init.sql"
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        sys.exit(1)

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Execute the schema
    try:
        async with engine.begin() as conn:
            # Split the schema into individual statements
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]

            for i, stmt in enumerate(statements, 1):
                if stmt:  # Skip empty statements
                    print(f"📝 Executing statement {i}/{len(statements)}...")
                    await conn.execute(text(stmt))

        print("✅ Database schema initialized successfully!")

        # Verify tables exist
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            tables = [row[0] for row in result.fetchall()]

        expected_tables = ['person_profile', 'intel_item', 'profile_link', 'audit_log',
                          'admin_user', 'ip_lookup_log', 'ip_ban_list']

        print("\n📋 Created tables:")
        for table in expected_tables:
            if table in tables:
                print(f"  ✅ {table}")
            else:
                print(f"  ❌ {table} (missing)")

        print("\n🎯 Next steps:")
        print("1. Create an admin user:")
        print("   INSERT INTO admin_user (email, hashed_password, role)")
        print("   VALUES ('admin@example.com', '$2b$12$your_bcrypt_hash', 'admin');")
        print("2. Start the application!")

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_database())