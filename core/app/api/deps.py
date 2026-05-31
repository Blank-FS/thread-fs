# app/api/deps.py

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.origin import normalize_origin
from app.db.session import get_async_session
from app.repositories.community import (
    get_community_by_public_key,
    is_origin_allowed_for_community,
)
from app.models.community import Community
from app.models.community_user import CommunityUser
from app.services import identity_service


async def require_valid_embed_context(
    session: AsyncSession = Depends(get_async_session),
    x_threadfs_community_key: str = Header(alias="X-ThreadFS-Community-Key"),
    origin: str | None = Header(default=None),
) -> Community:
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Origin header",
        )

    try:
        normalized_origin = normalize_origin(origin)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Origin header",
        )

    community = await get_community_by_public_key(
        session,
        public_key=x_threadfs_community_key,
    )

    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found",
        )

    is_allowed = await is_origin_allowed_for_community(
        session,
        community_id=community.id,
        origin=normalized_origin,
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed for this community",
        )

    return community


async def get_optional_current_community_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_async_session),
    community: Community = Depends(require_valid_embed_context),
):
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return None

    identity = await identity_service.verify_external_identity_token(
        session,
        community=community,
        token=token,
    )

    community_user = await identity_service.get_or_create_community_user_for_identity(
        session,
        community=community,
        identity=identity,
    )

    return community_user


async def require_current_community_user(
    community_user: CommunityUser | None = Depends(get_optional_current_community_user),
) -> CommunityUser:
    if not community_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return community_user
