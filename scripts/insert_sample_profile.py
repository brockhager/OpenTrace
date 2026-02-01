#!/usr/bin/env python3
"""
Insert sample profile into Railway PostgreSQL database
Run this after deploying to Railway: python scripts/insert_sample_profile.py
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


async def insert_sample_profile():
    """Insert the Michael Johnson sample profile."""
    print("🚀 Inserting sample Michael Johnson profile...")
    
    # Validate configuration
    try:
        settings.validate()
        print("✅ Database configuration validated")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("💡 Make sure DATABASE_URL is set (Railway provides this automatically)")
        sys.exit(1)

    # SQL to insert the sample profile
    insert_sql = """
    INSERT INTO person_profile (
      pfif_id, 
      author_name, 
      given_name, 
      family_name, 
      age, 
      sex,
      last_seen_location, 
      status, 
      is_confirmed, 
      source_date, 
      profile_url
    ) VALUES (
      'opentrace.org/person.namus.MP24398',
      'NamUs',
      'Michael',
      'Johnson',
      34,
      'Male',
      'Los Angeles, California',
      'missing',
      true,
      '2024-01-15',
      'https://www.namus.gov/MissingPersons/Case#24398'
    ) ON CONFLICT (pfif_id) DO NOTHING;
    """
    
    try:
        async with engine.begin() as conn:
            await conn.execute(text(insert_sql))
            print("✅ Sample profile inserted successfully!")
            
            # Verify the insertion
            result = await conn.execute(text("SELECT given_name, family_name FROM person_profile WHERE pfif_id = 'opentrace.org/person.namus.MP24398'"))
            profile = result.fetchone()
            
            if profile:
                print(f"🎯 Verified: {profile[0]} {profile[1]} is now in the database")
                print("🔍 Search for 'Michael Johnson' to see the magic!")
            else:
                print("⚠️ Profile insertion may have failed")
                
    except Exception as e:
        print(f"❌ Database insertion failed: {e}")
        sys.exit(1)


async def create_admin_user():
    """Create the default admin user."""
    print("\n👤 Creating admin user...")
    
    # Hashed password for 'admin123' using bcrypt
    admin_sql = """
    INSERT INTO admin_user (email, hashed_password, role)
    VALUES ('admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6QJw/2Ej7W', 'admin')
    ON CONFLICT (email) DO NOTHING;
    """
    
    try:
        async with engine.begin() as conn:
            await conn.execute(text(admin_sql))
            print("✅ Admin user created/verified!")
            print("🔐 Login: admin@example.com / admin123")
            
    except Exception as e:
        print(f"❌ Admin user creation failed: {e}")


if __name__ == "__main__":
    print("🌍 OpenTrace Database Setup")
    print("=" * 40)
    
    asyncio.run(insert_sample_profile())
    asyncio.run(create_admin_user())
    
    print("\n🎉 Setup complete!")
    print("👉 Test at: https://your-app-url.railway.app/")
    print("🔍 Search for: Michael Johnson")
