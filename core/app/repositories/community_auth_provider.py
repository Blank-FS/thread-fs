# app/repositories/community_auth_provider.py

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community_auth_provider import CommunityAuthProvider


async def get_auth_provider_by_issuer(
    session: AsyncSession,
    *,
    community_id: UUID,
    issuer: str,
) -> CommunityAuthProvider | None:
    result = await session.execute(
        select(CommunityAuthProvider).where(
            CommunityAuthProvider.community_id == community_id,
            CommunityAuthProvider.issuer == issuer,
            CommunityAuthProvider.revoked_at.is_(None),
        )
    )

    return result.scalar_one_or_none()
