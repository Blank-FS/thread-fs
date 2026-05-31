# app/services/comment_mutation_service.py

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sanitize import sanitize_comment_html
from app.core.common import utc_now
from app.models.community import Community
from app.models.community_user import CommunityUser
from app.repositories import comment as comment_repo
from app.repositories import thread as thread_repo


async def _get_owned_visible_comment(
    session: AsyncSession,
    *,
    community: Community,
    community_user: CommunityUser,
    comment_id: int,
):
    comment = await comment_repo.get_comment_by_id(session, comment_id)

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    thread = await thread_repo.get_thread_by_id(session, comment.thread_id)

    if not thread or thread.community_id != community.id or thread.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    if comment.community_user_id != community_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify your own comments",
        )

    if comment.status != "visible":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment is not editable",
        )

    return comment


async def edit_own_comment(
    session: AsyncSession,
    *,
    community: Community,
    community_user: CommunityUser,
    comment_id: int,
    content: str,
):
    comment = await _get_owned_visible_comment(
        session,
        community=community,
        community_user=community_user,
        comment_id=comment_id,
    )

    clean_content = sanitize_comment_html(content)

    comment.content = clean_content
    comment.edited_at = utc_now()
    comment.modified_at = utc_now()

    await session.commit()

    updated = await comment_repo.get_comment_by_id(session, comment.id)

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load updated comment",
        )

    return updated


async def delete_own_comment(
    session: AsyncSession,
    *,
    community: Community,
    community_user: CommunityUser,
    comment_id: int,
):
    comment = await _get_owned_visible_comment(
        session,
        community=community,
        community_user=community_user,
        comment_id=comment_id,
    )

    now = utc_now()

    comment.status = "deleted"
    comment.content = ""
    comment.deleted_at = now
    comment.deleted_by_user_id = community_user.id
    comment.modified_at = now

    # Optional: zero votes on deleted comments.
    comment.upvote_count = 0
    comment.downvote_count = 0

    await session.commit()

    deleted = await comment_repo.get_comment_by_id(session, comment.id)

    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load deleted comment",
        )

    return deleted
