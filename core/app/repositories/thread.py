# app/models/thread.py

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thread import Thread


async def get_thread_by_id(
    session: AsyncSession,
    thread_id: int,
) -> Thread | None:
    result = await session.execute(select(Thread).where(Thread.id == thread_id))
    return result.scalar_one_or_none()


async def get_thread_by_unique_id(
    session: AsyncSession,
    *,
    community_id: UUID,
    unique_id: str,
) -> Thread | None:
    result = await session.execute(
        select(Thread).where(
            Thread.community_id == community_id,
            Thread.unique_id == unique_id,
        )
    )
    return result.scalar_one_or_none()


async def create_thread(
    session: AsyncSession,
    *,
    community_id: UUID,
    unique_id: str,
    title: str | None,
    source_url: str | None,
) -> Thread:
    thread = Thread(
        community_id=community_id,
        unique_id=unique_id,
        title=title,
        source_url=source_url,
    )

    session.add(thread)
    await session.flush()
    await session.refresh(thread)

    return thread
