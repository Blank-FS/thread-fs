# app/models/comment.py

from collections import Counter
from typing import Literal
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.models.comment import Comment
from app.models.community_user import CommunityUser
from app.models.thread import Thread

CommentSort = Literal["latest", "oldest", "top"]

# What a thread can list: deleted and hidden comments keep their place while replies hang off them (their text is
# withheld by comment_service.present_comments); shown_in_thread decides which do
THREAD_STATUSES = ["visible", "deleted", "hidden"]


def shown_in_thread(viewer: CommunityUser | None):
    """Which comments a thread lists for this viewer: visible ones, and a deleted or removed one only while something
    visible is below it (reply_count counts visible comments only), as Reddit does. Its author still sees their own
    removed comment, with the reason, so a removal is never silent, and staff see every removed comment, to moderate
    the thread in place."""
    shown = or_(
        Comment.status == "visible",
        and_(Comment.status.in_(THREAD_STATUSES), Comment.reply_count > 0),
    )
    if viewer is not None and viewer.staff_role:
        return or_(shown, Comment.status == "hidden")
    if viewer is not None:
        shown = or_(shown, and_(Comment.status == "hidden", Comment.community_user_id == viewer.id))
    return shown


def is_shown_in_thread(comment: Comment, viewer: CommunityUser | None) -> bool:
    """shown_in_thread for one loaded comment."""
    if comment.status == "visible":
        return True
    if comment.status not in THREAD_STATUSES:
        return False
    if comment.reply_count > 0:
        return True
    if comment.status != "hidden" or viewer is None:
        return False
    return bool(viewer.staff_role) or comment.community_user_id == viewer.id


async def shift_visible_counts(session: AsyncSession, comments: list[Comment], delta: int) -> None:
    """Comments that just became visible (+1) or stopped being (-1): every comment above each one, and its thread,
    count it in or out (reply_count and comment_count count visible comments only). One statement for the comments,
    whatever the batch, done in SQL so concurrent changes add up; loaded ancestors keep their old counts in memory."""
    if not comments:
        return

    up = (
        select(Comment.parent_comment_id.label("ancestor_id"))
        .where(Comment.id.in_([comment.id for comment in comments]), Comment.parent_comment_id.is_not(None))
        .cte("up", recursive=True)
    )
    parent = aliased(Comment)
    up = up.union_all(
        select(parent.parent_comment_id)
        .join(up, parent.id == up.c.ancestor_id)
        .where(parent.parent_comment_id.is_not(None))
    )
    counts = select(up.c.ancestor_id, func.count().label("n")).group_by(up.c.ancestor_id).subquery()
    await session.execute(
        update(Comment)
        .where(Comment.id == counts.c.ancestor_id)
        .values(reply_count=Comment.reply_count + counts.c.n * delta)
        .execution_options(synchronize_session=False)
    )

    for thread_id, n in Counter(comment.thread_id for comment in comments).items():
        await session.execute(
            update(Thread)
            .where(Thread.id == thread_id)
            .values(comment_count=Thread.comment_count + n * delta)
            .execution_options(synchronize_session=False)
        )


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
    viewer: CommunityUser | None,
) -> int:
    result = await session.execute(
        select(func.count(Comment.id)).where(
            Comment.thread_id == thread_id,
            Comment.parent_comment_id.is_(None)
            if parent_comment_id is None
            else Comment.parent_comment_id == parent_comment_id,
            shown_in_thread(viewer),
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
    viewer: CommunityUser | None,
) -> list[Comment]:
    result = await session.execute(
        select(Comment)
        .options(selectinload(Comment.community_user))
        .where(
            Comment.thread_id == thread_id,
            Comment.parent_comment_id.is_(None)
            if parent_comment_id is None
            else Comment.parent_comment_id == parent_comment_id,
            shown_in_thread(viewer),
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
    viewer: CommunityUser | None,
) -> dict[int, int]:
    """How many direct replies each comment has, as count_comments counts them, in one query."""
    if not parent_comment_ids:
        return {}

    result = await session.execute(
        select(Comment.parent_comment_id, func.count(Comment.id))
        .where(
            Comment.parent_comment_id.in_(parent_comment_ids),
            shown_in_thread(viewer),
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
