# app/models/comment_vote.py

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment_vote import CommentVote


async def get_comment_vote(
    session: AsyncSession,
    *,
    comment_id: int,
    community_user_id: UUID,
) -> CommentVote | None:
    result = await session.execute(
        select(CommentVote).where(
            CommentVote.comment_id == comment_id,
            CommentVote.community_user_id == community_user_id,
        )
    )

    return result.scalar_one_or_none()


async def create_comment_vote(
    session: AsyncSession,
    *,
    comment_id: int,
    community_user_id: UUID,
    value: int,
) -> CommentVote:
    vote = CommentVote(
        comment_id=comment_id,
        community_user_id=community_user_id,
        value=value,
    )

    session.add(vote)
    await session.flush()

    return vote


async def list_votes_for_comments(
    session: AsyncSession,
    *,
    comment_ids: list[int],
    community_user_id,
) -> dict[int, int]:
    if not comment_ids:
        return {}

    result = await session.execute(
        select(CommentVote.comment_id, CommentVote.value).where(
            CommentVote.comment_id.in_(comment_ids),
            CommentVote.community_user_id == community_user_id,
        )
    )

    return {comment_id: value for comment_id, value in result.all()}
