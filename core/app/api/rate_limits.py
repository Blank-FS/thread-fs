# app/api/rate_limits.py

from fastapi import Depends, Request

from app.api.deps import (
    get_optional_current_community_user,
    require_current_community_user,
    require_valid_embed_context,
)
from app.core.config import settings
from app.core.rate_limit import check_ip_rate_limit, check_user_rate_limit
from app.models.community import Community
from app.models.community_user import CommunityUser


async def limit_read_comments(
    request: Request,
    community: Community = Depends(require_valid_embed_context),
    community_user: CommunityUser | None = Depends(get_optional_current_community_user),
) -> Community:
    if community_user:
        check_user_rate_limit(
            community_id=str(community.id),
            community_user_id=str(community_user.id),
            name="read_comments_user",
            limit=settings.RATE_LIMIT_READ_PER_MINUTE,
            window_seconds=60,
        )
    else:
        check_ip_rate_limit(
            request,
            name="read_comments_ip",
            limit=settings.RATE_LIMIT_READ_PER_MINUTE,
            window_seconds=60,
        )

    return community


async def limit_create_comment(
    community: Community = Depends(require_valid_embed_context),
    community_user: CommunityUser = Depends(require_current_community_user),
) -> tuple[Community, CommunityUser]:
    check_user_rate_limit(
        community_id=str(community.id),
        community_user_id=str(community_user.id),
        name="create_comment",
        limit=settings.RATE_LIMIT_COMMENT_CREATE_PER_MINUTE,
        window_seconds=60,
    )

    return community, community_user


async def limit_vote_comment(
    community: Community = Depends(require_valid_embed_context),
    community_user: CommunityUser = Depends(require_current_community_user),
) -> tuple[Community, CommunityUser]:
    check_user_rate_limit(
        community_id=str(community.id),
        community_user_id=str(community_user.id),
        name="vote_comment",
        limit=settings.RATE_LIMIT_VOTE_PER_MINUTE,
        window_seconds=60,
    )

    return community, community_user


async def limit_edit_comment(
    community: Community = Depends(require_valid_embed_context),
    community_user: CommunityUser = Depends(require_current_community_user),
) -> tuple[Community, CommunityUser]:
    check_user_rate_limit(
        community_id=str(community.id),
        community_user_id=str(community_user.id),
        name="edit_comment",
        limit=settings.RATE_LIMIT_COMMENT_EDIT_PER_HOUR,
        window_seconds=60 * 60,
    )

    return community, community_user


async def limit_delete_comment(
    community: Community = Depends(require_valid_embed_context),
    community_user: CommunityUser = Depends(require_current_community_user),
) -> tuple[Community, CommunityUser]:
    check_user_rate_limit(
        community_id=str(community.id),
        community_user_id=str(community_user.id),
        name="delete_comment",
        limit=settings.RATE_LIMIT_COMMENT_DELETE_PER_HOUR,
        window_seconds=60 * 60,
    )

    return community, community_user
