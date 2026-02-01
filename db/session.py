# db/session.py
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings

DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL:
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
else:
    engine = None
    async_session = None

async def get_db_session():
    if async_session is None:
        raise RuntimeError("DATABASE_URL is not configured. Set DATABASE_URL or RAILWAY_DATABASE_URL before using the DB.")
    async with async_session() as session:
        yield session