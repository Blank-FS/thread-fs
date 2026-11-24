# app/models/thread.py

from uuid import UUID
from sqlalchemy import bindparam, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import utc_now
from app.models.thread import Thread


async def get_thread_by_id(
    session: AsyncSession,
    thread_id: int,
) -> Thread | None:
    result = await session.execute(select(Thread).where(Thread.id == thread_id))
    return result.scalar_one_or_none()


# Built once, as every read runs it (app.repositories.comment)
BY_UNIQUE_ID = select(Thread).where(
    Thread.community_id == bindparam("community_id"),
    Thread.unique_id == bindparam("unique_id"),
)


async def get_thread_by_unique_id(
    session: AsyncSession,
    *,
    community_id: UUID,
    unique_id: str,
) -> Thread | None:
    result = await session.execute(BY_UNIQUE_ID, {"community_id": community_id, "unique_id": unique_id})
    return result.scalar_one_or_none()


async def touch_thread(session: AsyncSession, thread_id: int) -> None:
    """Marks a thread changed, so pages of it made before aren't shared any more (comment_page_service)."""
    await session.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(modified_at=utc_now())
        .execution_options(synchronize_session=False)
    )


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
