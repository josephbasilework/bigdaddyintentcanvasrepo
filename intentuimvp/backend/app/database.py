"""Database connection and session management."""

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


# Convert sync URL to async URL
async_database_url = settings.database_url.replace(
    "sqlite://", "sqlite+aiosqlite://"
).replace(
    "postgresql://", "postgresql+asyncpg://"
)

# Create async engine
async_engine = create_async_engine(
    async_database_url,
    echo=settings.debug,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Create sync engine (for backwards compatibility)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    echo=settings.debug,
)

# Create sync session factory (for backwards compatibility)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session for dependency injection.

    Yields:
        AsyncSession: SQLAlchemy async session

    Example:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_db() -> Generator[Session, None, None]:
    """Get database session for dependency injection (sync).

    Yields:
        Session: SQLAlchemy session

    Example:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
