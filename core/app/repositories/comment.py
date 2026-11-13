# app/models/comment.py

from typing import Literal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.thread import Thread

CommentSort = Literal["latest", "oldest", "top"]

# What a thread lists: deleted and hidden comments keep their place so replies stay attached (their text is withheld
# by comment_service.present_comments)
THREAD_STATUSES = ["visible", "deleted", "hidden"]
# A person's own list of comments: they still see ones moderators removed (others' view of it is visible ones only)
OWN_STATUSES = ["visible", "hidden"]


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
            Comment.status.in_(THREAD_STATUSES),
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
            Comment.status.in_(THREAD_STATUSES),
        )
        .order_by(*_comment_order_by(sort))
        .limit(limit)
        .offset(offset)
    )

    return list(result.scalars().all())


async def list_reply_previews(
    session: AsyncSession,
    *,
    parent_comment_ids: list[int],
    per_parent: int,
) -> list[Comment]:
    """The best few direct replies of each comment, in one query: highest score first, then the first posted. Visible
    ones only, since a removed or deleted reply isn't worth previewing."""
    if not parent_comment_ids or per_parent <= 0:
        return []

    score = Comment.upvote_count - Comment.downvote_count
    ranked = (
        select(
            Comment.id.label("id"),
            func.row_number()
            .over(
                partition_by=Comment.parent_comment_id,
                order_by=(score.desc(), Comment.created_at.asc(), Comment.id.asc()),
            )
            .label("rank"),
        )
        .where(
            Comment.parent_comment_id.in_(parent_comment_ids),
            Comment.status == "visible",
        )
        .subquery()
    )
    result = await session.execute(
        select(Comment)
        .join(ranked, ranked.c.id == Comment.id)
        .where(ranked.c.rank <= per_parent)
        .options(selectinload(Comment.community_user))
        .order_by(Comment.parent_comment_id, ranked.c.rank)
    )

    return list(result.scalars().all())


async def count_direct_replies(
    session: AsyncSession,
    *,
    parent_comment_ids: list[int],
) -> dict[int, int]:
    """How many direct replies each comment has, as count_comments counts them, in one query."""
    if not parent_comment_ids:
        return {}

    result = await session.execute(
        select(Comment.parent_comment_id, func.count(Comment.id))
        .where(
            Comment.parent_comment_id.in_(parent_comment_ids),
            Comment.status.in_(THREAD_STATUSES),
        )
        .group_by(Comment.parent_comment_id)
    )

    return {parent_id: int(count) for parent_id, count in result.all()}


async def count_comments_by_community_user(
    session: AsyncSession,
    *,
    community_user_id,
    community_id,
    include_hidden: bool = False,
) -> int:
    result = await session.execute(
        select(func.count(Comment.id))
        .join(Thread, Thread.id == Comment.thread_id)
        .where(
            Comment.community_user_id == community_user_id,
            Thread.community_id == community_id,
            Comment.status.in_(OWN_STATUSES if include_hidden else ["visible"]),
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
    include_hidden: bool = False,
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
            Comment.status.in_(OWN_STATUSES if include_hidden else ["visible"]),
        )
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(result.scalars().all())


async def get_comments_by_ids(session: AsyncSession, comment_ids) -> list[Comment]:
    """Several comments with their authors, in one query."""
    ids = list(set(comment_ids))
    if not ids:
        return []
    result = await session.execute(
        select(Comment).where(Comment.id.in_(ids)).options(selectinload(Comment.community_user))
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
    gif: dict | None = None,
    image: dict | None = None,
    parent_comment_id: int | None = None,
    ip_hash: str | None = None,
    user_agent: str | None = None,
    source: str | None = None,
    client: str | None = None,
) -> Comment:
    comment = Comment(
        thread_id=thread_id,
        community_user_id=community_user_id,
        parent_comment_id=parent_comment_id,
        content=content,
        gif=gif,
        image=image,
        status="visible",
        ip_hash=ip_hash,
        user_agent=user_agent,
        source=source,
        client=client,
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
