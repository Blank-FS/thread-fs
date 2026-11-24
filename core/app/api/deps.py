# app/api/deps.py

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.origin import normalize_origin
from app.db.session import get_async_session
from app.models.community import Community
from app.models.community_user import CommunityUser
from app.services import community_context, identity_service, moderation_service
from app.services.community_context import CommunityContext


async def require_community_context(
    session: AsyncSession = Depends(get_async_session),
    x_threadfs_community_key: str = Header(alias="X-ThreadFS-Community-Key"),
    origin: str | None = Header(default=None),
) -> CommunityContext:
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

    context = await community_context.get_by_public_key(session, x_threadfs_community_key)

    if normalized_origin not in context.origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed for this community",
        )

    return context


async def require_valid_embed_context(
    context: CommunityContext = Depends(require_community_context),
) -> Community:
    """The community, for reading: it's remembered between requests, so changes to it aren't saved (require_moderator's
    are)."""
    return context.community


async def get_optional_current_community_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_async_session),
    context: CommunityContext = Depends(require_community_context),
):
    community = context.community

    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return None

    identity = identity_service.verify_external_identity_token(
        providers=context.providers,
        token=token,
    )

    community_user = await identity_service.get_or_create_community_user_for_identity(
        session,
        community=community,
        identity=identity,
    )

    # From this request's token, never stored: taking a role away only needs the host to stop signing it
    community_user.staff_role = identity.staff_role

    # A ban suspends a moderator's powers too, so they can't lift it themselves. Admins can't be banned
    if identity.staff_role == "moderator" and await moderation_service.get_active_ban(
        session,
        community_id=community.id,
        community_user_id=community_user.id,
    ):
        community_user.staff_role = None

    community_user.signed_threads = identity.signed_threads
    community_user.thread_claim = identity.thread_claim

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


async def require_moderator(
    session: AsyncSession = Depends(get_async_session),
    remembered: Community = Depends(require_valid_embed_context),
    community_user: CommunityUser = Depends(require_current_community_user),
) -> tuple[Community, CommunityUser]:
    if community_user.staff_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator permissions required",
        )

    # As it is now, in this session: admins change it
    community = await session.get(Community, remembered.id)
    if community is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found",
        )

    return community, community_user


async def require_admin(
    context: tuple[Community, CommunityUser] = Depends(require_moderator),
) -> tuple[Community, CommunityUser]:
    if context[1].staff_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required",
        )

    return context
