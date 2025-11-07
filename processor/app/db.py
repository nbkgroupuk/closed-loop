# app/db.py
# Async SQLAlchemy database session manager
import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Default: local SQLite (override with DATABASE_URL in environment)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./processor_debug.db")

# Create async engine & session factory
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

@asynccontextmanager
async def get_session():
    """Yield a database session for use with async SQLAlchemy."""
    async with AsyncSessionLocal() as session:
        yield session
