# app/models/community_user.py

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community_user import CommunityUser


async def get_by_external_id(
    session: AsyncSession,
    *,
    community_id: UUID,
    external_user_id: str,
) -> CommunityUser | None:
    result = await session.execute(
        select(CommunityUser).where(
            CommunityUser.community_id == community_id,
            CommunityUser.external_user_id == external_user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_community_user_by_identity(
    session: AsyncSession,
    *,
    community_id: UUID,
    identity_provider: str,
    external_user_id: str,
) -> CommunityUser | None:
    result = await session.execute(
        select(CommunityUser).where(
            CommunityUser.community_id == community_id,
            CommunityUser.identity_provider == identity_provider,
            CommunityUser.external_user_id == external_user_id,
        )
    )

    return result.scalar_one_or_none()


async def create_community_user(
    session: AsyncSession,
    *,
    community_id: UUID,
    identity_provider: str,
    external_user_id: str,
    display_name: str | None,
    avatar_url: str | None,
    threadfs_user_id: UUID | None = None,
) -> CommunityUser:
    community_user = CommunityUser(
        community_id=community_id,
        identity_provider=identity_provider,
        external_user_id=external_user_id,
        display_name=display_name,
        avatar_url=avatar_url,
        threadfs_user_id=threadfs_user_id,
    )

    session.add(community_user)
    await session.flush()
    await session.refresh(community_user)

    return community_user
