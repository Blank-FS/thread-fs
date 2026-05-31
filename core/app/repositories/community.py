# app/repositories/community.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.community_api_key import CommunityApiKey
from app.models.community_allowed_origin import CommunityAllowedOrigin


async def get_community_by_public_key(
    session: AsyncSession,
    public_key: str,
) -> Community | None:
    result = await session.execute(
        select(Community)
        .join(CommunityApiKey, CommunityApiKey.community_id == Community.id)
        .where(
            CommunityApiKey.public_key == public_key,
            CommunityApiKey.revoked_at.is_(None),
        )
    )

    return result.scalar_one_or_none()

async def is_origin_allowed_for_community(
    session: AsyncSession,
    *,
    community_id,
    origin: str,
) -> bool:
    result = await session.execute(
        select(CommunityAllowedOrigin.id).where(
            CommunityAllowedOrigin.community_id == community_id,
            CommunityAllowedOrigin.origin == origin,
        )
    )

    return result.scalar_one_or_none() is not None