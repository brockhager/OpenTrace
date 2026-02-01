#!/usr/bin/env python3
"""
Phase 14 Deployment Script
Run this after deploying to Railway to migrate to the Location entity
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
from services.location_resolver import location_resolver


async def run_migration():
    """Run the Location table migration."""
    print("🚀 Running Phase 14: Location Entity Migration...")
    
    # Validate configuration
    try:
        settings.validate()
        print("✅ Database configuration validated")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Read and execute migration
    migration_path = project_root / "migrations" / "002_create_location_tables.sql"
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

        print("✅ Location tables migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


async def run_data_migration():
    """Run the location data migration from PersonProfile."""
    print("\n🔄 Running location data migration...")
    
    migration_path = project_root / "migrations" / "003_migrate_location_data.sql"
    if not migration_path.exists():
        print(f"❌ Data migration file not found: {migration_path}")
        return False

    with open(migration_path, 'r') as f:
        migration_sql = f.read()

    try:
        async with engine.begin() as conn:
            await conn.execute(text(migration_sql))
        
        print("✅ Location data migration completed!")
        return True
        
    except Exception as e:
        print(f"❌ Data migration failed: {e}")
        return False


async def verify_migration():
    """Verify the Location migration was successful."""
    print("\n🔍 Verifying Location migration...")
    
    try:
        async with engine.begin() as conn:
            # Check if location tables exist
            result = await conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' AND tablename IN ('location', 'person_location')
            """))
            tables = [row[0] for row in result.fetchall()]
            
            expected_tables = ['location', 'person_location']
            for table in expected_tables:
                if table in tables:
                    print(f"✅ Table {table} exists")
                else:
                    print(f"❌ Table {table} missing")
                    return False
            
            # Check PostGIS extension
            result = await conn.execute(text("""
                SELECT extname FROM pg_extension WHERE extname = 'postgis'
            """))
            postgis = result.fetchone()
            
            if postgis:
                print("✅ PostGIS extension enabled")
            else:
                print("⚠️ PostGIS extension not found (spatial queries may not work)")
            
            # Check location count
            result = await conn.execute(text("SELECT COUNT(*) FROM location"))
            location_count = result.scalar()
            print(f"📍 Locations created: {location_count}")
            
            # Check person-location relationships
            result = await conn.execute(text("SELECT COUNT(*) FROM person_location"))
            relationship_count = result.scalar()
            print(f"🔗 Person-location relationships: {relationship_count}")
            
            # Test spatial index
            if location_count > 0:
                result = await conn.execute(text("""
                    SELECT COUNT(*) FROM location 
                    WHERE ST_DWithin(
                        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
                        ST_SetSRID(ST_MakePoint(-118.2437, 34.0522), 4326),
                        50000  -- 50km around Los Angeles
                    )
                """))
                nearby_count = result.scalar()
                print(f"🗺️ Locations near Los Angeles (50km): {nearby_count}")
            
            return True
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


async def test_geocoding():
    """Test the geocoding service."""
    print("\n🧪 Testing geocoding service...")
    
    try:
        # Test location resolution
        location = await location_resolver.resolve_location("Los Angeles, California")
        if location:
            print(f"✅ Geocoding test passed: {location.display_name}")
            print(f"   Coordinates: {location.latitude}, {location.longitude}")
            print(f"   Location ID: {location.location_id}")
            return True
        else:
            print("❌ Geocoding test failed: No location returned")
            return False
            
    except Exception as e:
        print(f"❌ Geocoding test failed: {e}")
        return False


async def test_sample_queries():
    """Test sample location-aware queries."""
    print("\n🔍 Testing location-aware queries...")
    
    try:
        async with engine.begin() as conn:
            # Test spatial query
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM person p
                JOIN person_location pl ON p.pfif_id = pl.pfif_id
                JOIN location l ON pl.location_id = l.location_id
                WHERE p.is_confirmed = true 
                  AND ST_DWithin(
                      ST_SetSRID(ST_MakePoint(l.longitude, l.latitude), 4326),
                      ST_SetSRID(ST_MakePoint(-118.2437, 34.0522), 4326),
                      100000  -- 100km around Los Angeles
                  )
            """))
            count = result.scalar()
            print(f"✅ Spatial query test: {count} confirmed persons near Los Angeles")
            
            # Test location search
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM location 
                WHERE display_name ILIKE '%los angeles%' OR locality ILIKE '%los angeles%'
            """))
            location_count = result.scalar()
            print(f"✅ Location search test: {location_count} Los Angeles locations")
            
            return True
            
    except Exception as e:
        print(f"❌ Query test failed: {e}")
        return False


async def main():
    """Run complete Phase 14 deployment."""
    print("🌍 OpenTrace Phase 14: Location Entity Deployment")
    print("=" * 50)
    
    # Run table migration
    await run_migration()
    
    # Run data migration
    if await run_data_migration():
        print("✅ Data migration successful")
    else:
        print("⚠️ Data migration had issues, but continuing...")
    
    # Verify migration
    if await verify_migration():
        print("✅ Migration verification passed")
    else:
        print("❌ Migration verification failed")
        sys.exit(1)
    
    # Test geocoding
    if await test_geocoding():
        print("✅ Geocoding service working")
    else:
        print("⚠️ Geocoding service issues detected")
    
    # Test queries
    if await test_sample_queries():
        print("✅ Location queries working")
    else:
        print("⚠️ Location query issues detected")
    
    print("\n🎉 Phase 14 deployment completed!")
    print("👉 Test the new Location features:")
    print("   - Location-aware search: /search?q=Michael&location=Los Angeles")
    print("   - Spatial search: /search?lat=34.0522&lng=-118.2437&radius_km=50")
    print("   - Location resolution: POST /api/resolve-location")
    print("   - Nearby persons: GET /api/nearby?lat=34.0522&lng=-118.2437")
    print("   - Person locations: GET /api/persons/{pfif_id}/locations")


if __name__ == "__main__":
    asyncio.run(main())
