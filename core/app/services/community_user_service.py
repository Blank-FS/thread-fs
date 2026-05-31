# app/services/community_user_service.py

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import community_user as community_user_repo


async def get_or_create_community_user(
    session: AsyncSession,
    *,
    community_id: UUID,
    external_user_id: str,
    display_name: str | None = None,
    avatar_url: str | None = None,
):
    existing = await community_user_repo.get_by_external_id(
        session,
        community_id=community_id,
        external_user_id=external_user_id,
    )

    if existing:
        changed = False

        if display_name and existing.display_name != display_name:
            existing.display_name = display_name
            changed = True

        if avatar_url and existing.avatar_url != avatar_url:
            existing.avatar_url = avatar_url
            changed = True

        if changed:
            await session.commit()
            await session.refresh(existing)

        return existing

    community_user = await community_user_repo.create_community_user(
        session,
        community_id=community_id,
        external_user_id=external_user_id,
        display_name=display_name,
        avatar_url=avatar_url,
    )

    await session.commit()
    return community_user
