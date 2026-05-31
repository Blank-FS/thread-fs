# app/services/thread_service.py

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.repositories import thread as thread_repo


async def resolve_thread(
    session: AsyncSession,
    *,
    community: Community,
    thread_id: str,
):
    return await thread_repo.get_thread_by_unique_id(
        session,
        community_id=community.id,
        unique_id=thread_id,
    )
