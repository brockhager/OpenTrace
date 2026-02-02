#!/usr/bin/env python3
"""
Seed location database with US cities (population > 75,000)

Data source: US Census Bureau 2020 Census
Cities are major metropolitan areas, county seats, and significant municipalities.

Run: python -m scripts.seed_us_cities
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from decimal import Decimal

from core.config import settings
from models.location import Location, Base

# US Cities with population > 75,000 (2020 Census) - DEDUPED
US_CITIES = [
    ("New York", "New York", "NY", 40.7128, -74.0060, 8336817, "city"),
    ("Los Angeles", "California", "CA", 34.0522, -118.2437, 3979576, "city"),
    ("Chicago", "Illinois", "IL", 41.8781, -87.6298, 2693976, "city"),
    ("Houston", "Texas", "TX", 29.7604, -95.3698, 2320268, "city"),
    ("Phoenix", "Arizona", "AZ", 33.4484, -112.0742, 1680992, "city"),
    ("Philadelphia", "Pennsylvania", "PA", 39.9526, -75.1652, 1603797, "city"),
    ("San Antonio", "Texas", "TX", 29.4241, -98.4936, 1547253, "city"),
    ("San Diego", "California", "CA", 32.7157, -117.1611, 1423851, "city"),
    ("Dallas", "Texas", "TX", 32.7767, -96.7970, 1343573, "city"),
    ("San Jose", "California", "CA", 37.3382, -121.8863, 1021795, "city"),
    ("Austin", "Texas", "TX", 30.2672, -97.7431, 961855, "city"),
    ("Jacksonville", "Florida", "FL", 30.3322, -81.6557, 911507, "city"),
    ("Fort Worth", "Texas", "TX", 32.7555, -97.3308, 909585, "city"),
    ("Columbus", "Ohio", "OH", 39.9612, -82.9988, 898553, "city"),
    ("Indianapolis", "Indiana", "IN", 39.7684, -86.1581, 876384, "city"),
    ("Charlotte", "North Carolina", "NC", 35.2271, -80.8431, 885708, "city"),
    ("Seattle", "Washington", "WA", 47.6062, -122.3321, 753675, "city"),
    ("Denver", "Colorado", "CO", 39.7392, -104.9903, 715522, "city"),
    ("Washington", "District of Columbia", "DC", 38.9072, -77.0369, 705749, "city"),
    ("Boston", "Massachusetts", "MA", 42.3601, -71.0589, 692600, "city"),
    ("El Paso", "Texas", "TX", 31.7683, -106.4424, 678815, "city"),
    ("Nashville", "Tennessee", "TN", 36.1627, -86.7816, 715884, "city"),
    ("Detroit", "Michigan", "MI", 42.3314, -83.0458, 639111, "city"),
    ("Oklahoma City", "Oklahoma", "OK", 35.4676, -97.5164, 681054, "city"),
    ("Portland", "Oregon", "OR", 45.5152, -122.6784, 652503, "city"),
    ("Las Vegas", "Nevada", "NV", 36.1699, -115.1398, 644014, "city"),
    ("Memphis", "Tennessee", "TN", 35.1495, -90.0490, 633104, "city"),
    ("Louisville", "Kentucky", "KY", 38.2527, -85.7585, 633045, "city"),
    ("Baltimore", "Maryland", "MD", 39.2904, -76.6122, 585708, "city"),
    ("Milwaukee", "Wisconsin", "WI", 43.0389, -87.0852, 577222, "city"),
    ("Albuquerque", "New Mexico", "NM", 35.0853, -106.6504, 564559, "city"),
    ("Tucson", "Arizona", "AZ", 32.2217, -110.9265, 525796, "city"),
    ("Fresno", "California", "CA", 36.7469, -119.7726, 525010, "city"),
    ("San Francisco", "California", "CA", 37.7749, -122.4194, 873965, "city"),
    ("Sacramento", "California", "CA", 38.5816, -121.4944, 524943, "city"),
    ("Long Beach", "California", "CA", 33.7701, -118.1937, 462257, "city"),
    ("Kansas City", "Missouri", "MO", 39.0997, -94.5786, 508090, "city"),
    ("Corpus Christi", "Texas", "TX", 27.5730, -97.3964, 305215, "city"),
    ("Lexington", "Kentucky", "KY", 38.0297, -84.4784, 322570, "city"),
    ("Chandler", "Arizona", "AZ", 33.3062, -111.8413, 276228, "city"),
    ("Irvine", "California", "CA", 33.6846, -117.7289, 307670, "city"),
    ("Anaheim", "California", "CA", 33.8354, -117.9985, 346824, "city"),
    ("Aurora", "Colorado", "CO", 39.7294, -104.8202, 386289, "city"),
    ("Santa Ana", "California", "CA", 33.7455, -117.8677, 310127, "city"),
    ("Riverside", "California", "CA", 33.9425, -117.4125, 314998, "city"),
    ("Stockton", "California", "CA", 37.9577, -121.2911, 320545, "city"),
    ("San Bernardino", "California", "CA", 34.1083, -117.2898, 235805, "city"),
    ("Plano", "Texas", "TX", 33.0198, -96.6989, 285494, "city"),
    ("Garland", "Texas", "TX", 32.9126, -96.6428, 246873, "city"),
    ("Glendale", "Arizona", "AZ", 33.5417, -112.1852, 246709, "city"),
    ("Irving", "Texas", "TX", 32.8140, -96.9489, 239798, "city"),
    ("Baton Rouge", "Louisiana", "LA", 30.4583, -91.1871, 227818, "city"),
    ("North Las Vegas", "Nevada", "NV", 36.2009, -115.0993, 280514, "city"),
    ("Chula Vista", "California", "CA", 32.6401, -117.0842, 307396, "city"),
    ("Laredo", "Texas", "TX", 27.5306, -97.1964, 236091, "city"),
    ("Lubbock", "Texas", "TX", 33.5779, -101.8552, 249066, "city"),
    ("Winston-Salem", "North Carolina", "NC", 36.0999, -80.2442, 247945, "city"),
    ("Greensboro", "North Carolina", "NC", 36.0726, -79.7920, 290711, "city"),
    ("Madison", "Wisconsin", "WI", 43.0731, -89.4012, 269840, "city"),
    ("Huntsville", "Alabama", "AL", 34.7304, -86.5861, 215006, "city"),
    ("Orlando", "Florida", "FL", 28.5421, -81.3723, 307573, "city"),
    ("Tallahassee", "Florida", "FL", 30.4383, -84.2807, 196280, "city"),
    ("Reno", "Nevada", "NV", 39.5296, -119.8138, 248674, "city"),
    ("Spokane", "Washington", "WA", 47.6587, -117.4260, 228989, "city"),
    ("Scottsdale", "Arizona", "AZ", 33.4942, -111.9261, 258069, "city"),
    ("Gilbert", "Arizona", "AZ", 33.3528, -111.7890, 267918, "city"),
    ("Tampa", "Florida", "FL", 27.9506, -82.4572, 303895, "city"),
    ("Tempe", "Arizona", "AZ", 33.4255, -111.9400, 175526, "city"),
    ("Newark", "New Jersey", "NJ", 40.7357, -74.1724, 277140, "city"),
    ("Berkeley", "California", "CA", 37.8716, -122.2727, 121643, "city"),
    ("Arlington", "Texas", "TX", 32.7357, -97.2247, 394314, "city"),
    ("Cincinnati", "Ohio", "OH", 39.1581, -84.1616, 309317, "city"),
    ("Jersey City", "New Jersey", "NJ", 40.7282, -74.0776, 262146, "city"),
    ("Anchorage", "Alaska", "AK", 61.2181, -149.9003, 288000, "city"),
    ("St. Paul", "Minnesota", "MN", 44.9537, -93.0900, 311769, "city"),
    ("Pittsburgh", "Pennsylvania", "PA", 40.4406, -79.9959, 305841, "city"),
    ("Honolulu", "Hawaii", "HI", 21.3099, -157.8581, 345615, "city"),
    ("Fontana", "California", "CA", 34.0955, -117.4353, 222535, "city"),
    ("Durham", "North Carolina", "NC", 35.9940, -78.8986, 283506, "city"),
    ("Oxnard", "California", "CA", 34.1899, -119.1771, 216762, "city"),
    ("Modesto", "California", "CA", 37.6688, -121.0011, 218464, "city"),
    ("Huntington Beach", "California", "CA", 33.7614, -117.9988, 198711, "city"),
    ("Amarillo", "Texas", "TX", 35.0866, -101.6588, 199371, "city"),
    ("Grand Prairie", "Texas", "TX", 32.6646, -97.0081, 180396, "city"),
    ("Aurora", "Illinois", "IL", 41.7606, -88.3201, 180542, "city"),
    ("Yonkers", "New York", "NY", 40.9311, -73.8981, 211374, "city"),
    ("Moreno Valley", "California", "CA", 33.7522, -117.2311, 208634, "city"),
    ("Akron", "Ohio", "OH", 41.0814, -81.5186, 197542, "city"),
    ("Santa Clarita", "California", "CA", 34.3917, -118.6425, 228673, "city"),
    ("Shreveport", "Louisiana", "LA", 32.5252, -93.7372, 187395, "city"),
    ("Brownsville", "Texas", "TX", 25.9017, -97.4975, 183046, "city"),
    ("Overland Park", "Kansas", "KS", 38.9819, -94.6704, 173067, "city"),
    ("Rancho Cucamonga", "California", "CA", 34.1063, -117.5931, 174453, "city"),
    ("Providence", "Rhode Island", "RI", 41.8240, -71.4128, 179883, "city"),
    ("Jackson", "Mississippi", "MS", 32.2988, -90.1848, 153701, "city"),
    ("Oceanside", "California", "CA", 33.1964, -117.3794, 167086, "city"),
    ("Fort Wayne", "Indiana", "IN", 41.0787, -85.1289, 250665, "city"),
    ("Montgomery", "Alabama", "AL", 32.3672, -86.2999, 198218, "city"),
    ("Glendale", "California", "CA", 34.1454, -118.2482, 196543, "city"),
    ("Port St. Lucie", "Florida", "FL", 27.2426, -80.3550, 161851, "city"),
    ("Topeka", "Kansas", "KS", 39.0473, -95.6752, 127473, "city"),
    ("Norfolk", "Virginia", "VA", 36.8508, -76.2859, 238005, "city"),
    ("Coral Springs", "Florida", "FL", 26.2706, -80.2720, 121056, "city"),
    ("Paterson", "New Jersey", "NJ", 40.9161, -74.1743, 159349, "city"),
    ("Springfield", "Missouri", "MO", 37.2089, -93.2923, 167319, "city"),
    ("Spokane Valley", "Washington", "WA", 47.5304, -117.2559, 102405, "city"),
]


async def seed_locations():
    """Seed locations table with US cities."""
    
    if not settings.DATABASE_URL:
        print("❌ DATABASE_URL not set. Skipping seed.")
        return
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        # Create tables if they don't exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as session:
            # Check how many locations already exist
            result = await session.execute(select(Location))
            existing = result.scalars().all()
            existing_ids = {loc.location_id for loc in existing}
            
            print(f"📍 Found {len(existing)} existing locations")
            
            added_count = 0
            skipped_count = 0
            seen_in_seed = set()  # Track duplicates within the seed data itself
            
            for city_name, state, state_code, lat, lon, population, loc_type in US_CITIES:
                # Generate location_id: lowercase, dash-separated, include state code
                location_id = f"{city_name.lower().replace(' ', '-')}-{state_code.lower()}-usa"
                
                if location_id in existing_ids or location_id in seen_in_seed:
                    skipped_count += 1
                    continue
                
                seen_in_seed.add(location_id)
                
                # Create location
                location = Location(
                    location_id=location_id,
                    canonical_name=f"{city_name}, {state}, USA",
                    display_name=f"{city_name}, {state_code}",
                    short_name=state_code,
                    latitude=Decimal(str(lat)),
                    longitude=Decimal(str(lon)),
                    coordinate_precision="exact",
                    country_code="US",
                    country_name="United States",
                    admin1_code=state_code,
                    admin1_name=state,
                    locality=city_name,
                    location_type=loc_type,
                    is_active=True,
                    population=population
                )
                
                session.add(location)
                added_count += 1
                
                # Batch commit every 25 records
                if added_count % 25 == 0:
                    await session.commit()
                    print(f"✅ Added {added_count} locations...")
            
            # Final commit
            if added_count > 0:
                await session.commit()
            
            print(f"\n✅ Seeding complete!")
            print(f"   Added: {added_count}")
            print(f"   Skipped (already exist): {skipped_count}")
            print(f"   Total in DB: {len(existing) + added_count}")
    
    except Exception as e:
        print(f"❌ Error seeding locations: {e}")
        raise
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print("🌍 Seeding US cities (population > 75,000)...")
    asyncio.run(seed_locations())
