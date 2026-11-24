# app/services/community_context.py
"""What every request needs to know about its community: the community itself, its allowed origins, its auth providers
and its report reasons. They rarely change, so each worker remembers them for COMMUNITY_CACHE_SECONDS rather than
reading them for every request.

A change made through the moderation API applies at once in the worker that made it (clear). Anything else (other
workers, the scripts) can take that long to apply, revoking a key included."""

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ttl_cache import TTLCache
from app.models.community import Community
from app.models.community_allowed_origin import CommunityAllowedOrigin
from app.models.community_auth_provider import CommunityAuthProvider
from app.repositories.community import get_community_by_public_key
from app.services.reason_service import Reason, list_reasons


@dataclass(frozen=True)
class CommunityContext:
    # Detached from any session, so for reading only: a change to it would never be saved
    community: Community
    origins: frozenset[str]
    providers: dict[str, CommunityAuthProvider]
    reasons: list[Reason]


_cache: TTLCache[CommunityContext] = TTLCache(settings.COMMUNITY_CACHE_SECONDS, max_entries=500)


async def get_by_public_key(session: AsyncSession, public_key: str) -> CommunityContext:
    return await _cache.get(public_key, lambda: _load(session, public_key))


def clear() -> None:
    _cache.clear()


async def _load(session: AsyncSession, public_key: str) -> CommunityContext:
    community = await get_community_by_public_key(session, public_key=public_key)
    if community is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found",
        )

    origins = await session.execute(
        select(CommunityAllowedOrigin.origin).where(CommunityAllowedOrigin.community_id == community.id)
    )
    providers = await session.execute(
        select(CommunityAuthProvider).where(
            CommunityAuthProvider.community_id == community.id,
            CommunityAuthProvider.revoked_at.is_(None),
        )
    )
    providers = {provider.issuer: provider for provider in providers.scalars()}
    reasons = await list_reasons(session, community.id)

    for row in (community, *providers.values()):
        session.expunge(row)
    return CommunityContext(
        community=community,
        origins=frozenset(origins.scalars()),
        providers=providers,
        reasons=reasons,
    )
