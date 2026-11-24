# app/models/community_user.py

from uuid import UUID
from sqlalchemy import bindparam, select
from sqlalchemy.dialects.postgresql import insert
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


# Built once, as every signed-in request runs it (app.repositories.comment)
BY_IDENTITY = select(CommunityUser).where(
    CommunityUser.community_id == bindparam("community_id"),
    CommunityUser.identity_provider == bindparam("identity_provider"),
    CommunityUser.external_user_id == bindparam("external_user_id"),
)


async def get_community_user_by_identity(
    session: AsyncSession,
    *,
    community_id: UUID,
    identity_provider: str,
    external_user_id: str,
) -> CommunityUser | None:
    result = await session.execute(
        BY_IDENTITY,
        {
            "community_id": community_id,
            "identity_provider": identity_provider,
            "external_user_id": external_user_id,
        },
    )

    return result.scalar_one_or_none()


async def get_or_create_community_user(
    session: AsyncSession,
    *,
    community_id: UUID,
    identity_provider: str,
    external_user_id: str,
    display_name: str | None,
    avatar_url: str | None,
    avatar_frame_url: str | None = None,
    last_staff_role: str | None = None,
    threadfs_user_id: UUID | None = None,
) -> CommunityUser:
    """Creates a user, or returns the one another request created first."""
    await session.execute(
        insert(CommunityUser)
        .values(
            community_id=community_id,
            identity_provider=identity_provider,
            external_user_id=external_user_id,
            display_name=display_name,
            avatar_url=avatar_url,
            avatar_frame_url=avatar_frame_url,
            last_staff_role=last_staff_role,
            threadfs_user_id=threadfs_user_id,
        )
        .on_conflict_do_nothing(index_elements=["community_id", "identity_provider", "external_user_id"])
    )

    community_user = await get_community_user_by_identity(
        session,
        community_id=community_id,
        identity_provider=identity_provider,
        external_user_id=external_user_id,
    )
    if community_user is None:
        raise RuntimeError("The community user was deleted while being created")
    return community_user
