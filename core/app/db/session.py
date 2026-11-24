# app/db/session.py

from collections.abc import AsyncGenerator
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # settings.ENVIRONMENT == "development"
    **(
        {}
        if settings.DATABASE_URL.startswith("sqlite")
        else {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT_SECONDS,
            # The most recently used first, so ones opened for a burst go idle
            "pool_use_lifo": True,
        }
    ),
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

# The same connections without a transaction around them, for requests that only read: BEGIN and ROLLBACK would be two
# more round trips to the database each. A single write in one (a new viewer) commits by itself.
read_session_maker = async_sessionmaker(
    engine.execution_options(isolation_level="AUTOCOMMIT"),
    expire_on_commit=False,
)

# POSTs that only read
READ_POSTS = ("/embed/bootstrap", "/embed/threads/resolve")


async def get_async_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    reads = request.method == "GET" or request.url.path.endswith(READ_POSTS)
    async with (read_session_maker if reads else async_session_maker)() as session:
        yield session
