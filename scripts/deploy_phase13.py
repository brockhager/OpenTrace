#!/usr/bin/env python3
"""
Phase 13 Deployment Script
Run this after deploying to Railway to migrate to the new Person entity
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


async def run_migration():
    """Run the Person table migration."""
    print("🚀 Running Phase 13: Person Entity Migration...")
    
    # Validate configuration
    try:
        settings.validate()
        print("✅ Database configuration validated")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Read and execute migration
    migration_path = project_root / "migrations" / "001_create_person_table.sql"
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        sys.exit(1)

    with open(migration_path, 'r') as f:
        migration_sql = f.read()

    try:
        async with engine.begin() as conn:
            # Split the migration into individual statements
            statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]

            for i, stmt in enumerate(statements, 1):
                if stmt:
                    print(f"📝 Executing migration statement {i}/{len(statements)}...")
                    await conn.execute(text(stmt))

        print("✅ Person table migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


async def verify_migration():
    """Verify the Person table was created correctly."""
    print("\n🔍 Verifying migration...")
    
    try:
        async with engine.begin() as conn:
            # Check if person table exists
            result = await conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' AND tablename = 'person'
            """))
            person_table = result.fetchone()
            
            if not person_table:
                print("❌ Person table was not created")
                return False
            
            print("✅ Person table exists")
            
            # Check indexes
            result = await conn.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE schemaname = 'public' AND tablename = 'person'
            """))
            indexes = [row[0] for row in result.fetchall()]
            
            expected_indexes = ['idx_person_pfif_id', 'idx_person_names', 'idx_person_status', 
                              'idx_person_confirmed', 'idx_person_source', 'idx_person_active']
            
            for idx in expected_indexes:
                if any(idx in index_name for index_name in indexes):
                    print(f"✅ Index {idx} found")
                else:
                    print(f"⚠️ Index {idx} not found")
            
            return True
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


async def test_sample_insert():
    """Test inserting a sample Person record."""
    print("\n🧪 Testing sample Person insert...")
    
    try:
        async with engine.begin() as conn:
            # Insert sample Michael Johnson record
            await conn.execute(text("""
                INSERT INTO person (
                    pfif_id, given_name, family_name, age_at_disappearance, sex,
                    status, is_confirmed, primary_source, source_id, source_url,
                    source_confidence
                ) VALUES (
                    'opentrace.org/person/namus.MP24398',
                    'Michael',
                    'Johnson',
                    34,
                    'Male',
                    'missing',
                    true,
                    'namus',
                    'MP24398',
                    'https://namus.nij.ojp.gov/case/MP24398',
                    'high'
                ) ON CONFLICT (pfif_id) DO NOTHING
            """))
            
            print("✅ Sample Person record inserted")
            
            # Verify the insert
            result = await conn.execute(text("""
                SELECT given_name, family_name, is_confirmed 
                FROM person WHERE pfif_id = 'opentrace.org/person/namus.MP24398'
            """))
            person = result.fetchone()
            
            if person:
                print(f"✅ Verified: {person[0]} {person[1]} (confirmed: {person[2]})")
                return True
            else:
                print("❌ Sample record not found")
                return False
                
    except Exception as e:
        print(f"❌ Sample insert failed: {e}")
        return False


async def main():
    """Run complete Phase 13 deployment."""
    print("🌍 OpenTrace Phase 13: Person Entity Deployment")
    print("=" * 50)
    
    # Run migration
    await run_migration()
    
    # Verify migration
    if await verify_migration():
        print("✅ Migration verification passed")
    else:
        print("❌ Migration verification failed")
        sys.exit(1)
    
    # Test sample insert
    if await test_sample_insert():
        print("✅ Sample insert test passed")
    else:
        print("❌ Sample insert test failed")
        sys.exit(1)
    
    print("\n🎉 Phase 13 deployment completed successfully!")
    print("👉 Test the new Person entity:")
    print("   - Public search: /search?q=Michael")
    print("   - Admin review: /admin/review-persons")
    print("   - Approve person: /admin/approve-person")


if __name__ == "__main__":
    asyncio.run(main())
