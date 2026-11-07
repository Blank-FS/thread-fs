# tests/conftest.py

import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_async_session
from app.main import app


# The fixtures below drop the whole public schema, so these tests must never reach a real database. They run against
# TEST_DATABASE_URL if set, else the configured server's threadfs_test database, and refuse any database without
# "test" in its name.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or (
    settings.DATABASE_URL.rsplit("/", 1)[0] + "/threadfs_test"
)
if "test" not in TEST_DATABASE_URL.rsplit("/", 1)[-1]:
    pytest.exit(f"Refusing to run tests on a non-test database: {TEST_DATABASE_URL.rsplit('/', 1)[-1]}", returncode=2)


def to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if "ssl=true" in url:
        url = url.replace("ssl=true", "sslmode=require")
    if "ssl=require" in url:
        url = url.replace("ssl=require", "sslmode=require")
    return url


sync_engine = create_engine(
    to_sync_url(TEST_DATABASE_URL),
    echo=False,
    poolclass=NullPool,
)

async_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

TestSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_async_session] = override_get_async_session


@pytest.fixture(scope="session", autouse=True)
def create_test_schema() -> Generator[None, None, None]:
    with sync_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT USAGE, CREATE ON SCHEMA public TO PUBLIC"))
        Base.metadata.create_all(bind=conn)

    yield

    with sync_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT USAGE, CREATE ON SCHEMA public TO PUBLIC"))

    sync_engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables() -> Generator[None, None, None]:
    with sync_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )

    yield


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def cleanup_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()
