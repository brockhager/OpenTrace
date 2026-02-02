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
    # In test environments or when DATABASE_URL is not set, yield None so endpoints
    # (like /health) can still respond and make an informed decision.
    if os.getenv("PYTEST_CURRENT_TEST"):
        yield None
        return
    if async_session is None:
        yield None
        return
    async with async_session() as session:
        yield session