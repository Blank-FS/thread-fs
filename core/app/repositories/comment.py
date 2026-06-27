# app/models/comment.py

from typing import Literal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.thread import Thread

CommentSort = Literal["latest", "oldest", "top"]


def _comment_order_by(sort: CommentSort):
    if sort == "latest":
        return (Comment.created_at.desc(), Comment.id.desc())

    if sort == "top":
        return (
            (Comment.upvote_count - Comment.downvote_count).desc(),
            Comment.created_at.desc(),
            Comment.id.desc(),
        )

    # oldest
    return (Comment.created_at.asc(), Comment.id.asc())


async def count_comments(
    session: AsyncSession,
    *,
    thread_id: int,
    parent_comment_id: int | None,
) -> int:
    result = await session.execute(
        select(func.count(Comment.id)).where(
            Comment.thread_id == thread_id,
            Comment.parent_comment_id.is_(None)
            if parent_comment_id is None
            else Comment.parent_comment_id == parent_comment_id,
            Comment.status.in_(["visible", "deleted"]),
        )
    )

    return int(result.scalar_one())


async def list_comments(
    session: AsyncSession,
    *,
    thread_id: int,
    parent_comment_id: int | None,
    limit: int,
    offset: int,
    sort: CommentSort,
) -> list[Comment]:
    result = await session.execute(
        select(Comment)
        .options(selectinload(Comment.community_user))
        .where(
            Comment.thread_id == thread_id,
            Comment.parent_comment_id.is_(None)
            if parent_comment_id is None
            else Comment.parent_comment_id == parent_comment_id,
            Comment.status.in_(["visible", "deleted"]),
        )
        .order_by(*_comment_order_by(sort))
        .limit(limit)
        .offset(offset)
    )

    return list(result.scalars().all())


async def count_comments_by_community_user(
    session: AsyncSession,
    *,
    community_user_id,
    community_id,
) -> int:
    result = await session.execute(
        select(func.count(Comment.id))
        .join(Thread, Thread.id == Comment.thread_id)
        .where(
            Comment.community_user_id == community_user_id,
            Thread.community_id == community_id,
            Comment.status == "visible",
        )
    )

    return int(result.scalar_one())


async def list_comments_by_community_user(
    session: AsyncSession,
    *,
    community_user_id,
    community_id,
    limit: int,
    offset: int,
) -> list[Comment]:
    result = await session.execute(
        select(Comment)
        .join(Thread, Thread.id == Comment.thread_id)
        .options(
            selectinload(Comment.community_user),
            selectinload(Comment.thread),
        )
        .where(
            Comment.community_user_id == community_user_id,
            Thread.community_id == community_id,
            Comment.status == "visible",
        )
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(result.scalars().all())


async def get_comment_by_id(
    session: AsyncSession,
    comment_id: int,
) -> Comment | None:
    result = await session.execute(
        select(Comment)
        .options(selectinload(Comment.community_user))
        .where(Comment.id == comment_id)
    )

    return result.scalar_one_or_none()


async def create_comment(
    session: AsyncSession,
    *,
    thread_id: int,
    community_user_id,
    content: str,
    parent_comment_id: int | None = None,
    ip_hash: str | None = None,
    user_agent: str | None = None,
) -> Comment:
    comment = Comment(
        thread_id=thread_id,
        community_user_id=community_user_id,
        parent_comment_id=parent_comment_id,
        content=content,
        status="visible",
        ip_hash=ip_hash,
        user_agent=user_agent,
    )

    session.add(comment)
    await session.flush()
    await session.refresh(comment)

    return comment


async def get_comment_ancestor_chain(
    session: AsyncSession,
    *,
    comment: Comment,
) -> list[Comment]:
    ancestors: list[Comment] = []

    current = comment

    while current.parent_comment_id is not None:
        parent = await get_comment_by_id(session, current.parent_comment_id)

        if parent is None:
            break

        ancestors.append(parent)
        current = parent

    return ancestors
