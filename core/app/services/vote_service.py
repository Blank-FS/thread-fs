# app/services/vote_service.py

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.community_user import CommunityUser
from app.repositories import comment as comment_repo
from app.repositories import comment_vote as vote_repo
from app.repositories import thread as thread_repo


async def vote_on_comment(
    session: AsyncSession,
    *,
    community: Community,
    community_user: CommunityUser,
    comment_id: int,
    value: int,
):
    if value not in (-1, 0, 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vote value must be -1, 0, or 1",
        )

    comment = await comment_repo.get_comment_by_id(session, comment_id)

    if not comment or comment.status != "visible":
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

    if thread.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Thread is locked",
        )

    existing_vote = await vote_repo.get_comment_vote(
        session,
        comment_id=comment.id,
        community_user_id=community_user.id,
    )

    old_value = existing_vote.value if existing_vote else 0
    new_value = value

    if old_value == new_value:
        # Clicking the same vote again toggles it off.
        new_value = 0

    # Remove old count.
    if old_value == 1:
        comment.upvote_count = max(0, comment.upvote_count - 1)
    elif old_value == -1:
        comment.downvote_count = max(0, comment.downvote_count - 1)

    # Apply new count.
    if new_value == 1:
        comment.upvote_count += 1
    elif new_value == -1:
        comment.downvote_count += 1

    if existing_vote:
        existing_vote.value = new_value
    elif new_value != 0:
        await vote_repo.create_comment_vote(
            session,
            comment_id=comment.id,
            community_user_id=community_user.id,
            value=new_value,
        )

    await session.commit()

    updated = await comment_repo.get_comment_by_id(session, comment.id)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load updated comment",
        )

    # Attach transient field for response serialization.
    updated.viewer_vote = new_value or None

    return updated
