#!/usr/bin/env python3
"""Verify seeding results."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from core.config import settings
from models.location import Location

async def verify():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Location).where(Location.is_active == True))
        count = result.scalar()
        
        result2 = await session.execute(select(Location).where(Location.country_code == "US").limit(5))
        us_sample = result2.scalars().all()
        
        print(f"✅ Total active locations in DB: {count}")
        print(f"📍 Sample US cities:")
        for loc in us_sample:
            pop = f"({loc.population:,} people)" if loc.population else "(pop unknown)"
            print(f"   - {loc.display_name} {pop}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify())
