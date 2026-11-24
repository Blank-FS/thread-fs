# app/services/comment_page_service.py
"""A thread's comments as a viewer sees them: a page of them, and one comment in its context.

Nearly everyone sees the same page. A signed-in viewer's differs only in their own votes, and in their own comments that
moderators removed; only staff see more. So pages are shared for READ_CACHE_SECONDS (shared_page), and what costs a
request is the viewer, their votes and whether they have removed comments, all quick to look up."""

from collections.abc import Hashable

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ttl_cache import TTLCache
from app.models.comment import Comment
from app.models.community import Community
from app.models.community_user import CommunityUser
from app.models.thread import Thread
from app.repositories import comment as comment_repo
from app.repositories import comment_vote as vote_repo
from app.repositories.comment import CommentSort
from app.schemas.embed import CommentContextRead, CommentTreeRead, PageResponse
from app.services.comment_service import present_comments


def require_may_read(community: Community, viewer: CommunityUser | None) -> None:
    if not community.allow_anonymous_read and not viewer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to read comments",
        )


# Pages as plain data, as everyone without votes or removed comments of their own sees them
_shared_pages: TTLCache[dict] = TTLCache(settings.READ_CACHE_SECONDS, max_entries=200)


async def page_for(
    session: AsyncSession,
    *,
    thread: Thread | None,
    viewer: CommunityUser | None,
    parent_comment_id: int | None,
    limit: int,
    offset: int,
    sort: CommentSort | None,
    reply_preview: int,
) -> dict:
    """load_page as plain data, shared between viewers when theirs is the same but for their votes."""

    async def load(viewer: CommunityUser | None) -> dict:
        page = await load_page(
            session,
            thread=thread,
            viewer=viewer,
            parent_comment_id=parent_comment_id,
            limit=limit,
            offset=offset,
            sort=sort,
            reply_preview=reply_preview,
        )
        return page.model_dump(mode="json")

    if (
        thread is None
        or viewer is not None
        and (
            viewer.staff_role
            or await comment_repo.has_hidden_in_thread(session, thread_id=thread.id, community_user_id=viewer.id)
        )
    ):
        return await load(viewer)

    # A thread's modified_at moves with every comment posted, edited, deleted, removed or restored in it, so the viewer's
    # own changes show at once. Only vote counts (and authors' new avatars) can be a few seconds old
    key: Hashable = (thread.id, thread.modified_at, parent_comment_id, limit, offset, sort, reply_preview)
    page = await _shared_pages.get(key, lambda: load(None))
    if viewer is None:
        return page

    ids = [comment["id"] for item in page["items"] for comment in (item, *item["replies"])]
    votes = await vote_repo.list_votes_for_comments(session, comment_ids=ids, community_user_id=viewer.id)
    if not votes:
        return page

    # The page is everyone's, so the votes go on copies
    def with_vote(comment: dict) -> dict:
        return {**comment, "viewer_vote": votes.get(comment["id"])}

    return {
        **page,
        "items": [
            {**with_vote(item), "replies": [with_vote(reply) for reply in item["replies"]]} for item in page["items"]
        ],
    }


async def load_page(
    session: AsyncSession,
    *,
    thread: Thread | None,
    viewer: CommunityUser | None,
    parent_comment_id: int | None,
    limit: int,
    offset: int,
    sort: CommentSort | None,
    reply_preview: int,
) -> PageResponse[CommentTreeRead]:
    # Important: read should not create a thread.
    if not thread:
        return PageResponse[CommentTreeRead](
            items=[],
            limit=limit,
            offset=offset,
            next_offset=None,
            has_more=False,
            total=0,
        )

    if thread.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    if parent_comment_id is not None:
        await _require_parent(session, thread, parent_comment_id)

    comments = await comment_repo.list_comments(
        session,
        thread_id=thread.id,
        parent_comment_id=parent_comment_id,
        limit=limit,
        offset=offset,
        sort=sort or ("oldest" if parent_comment_id is not None else "latest"),
        viewer=viewer,
    )

    # A page that isn't full is the last one, so the total is known without counting
    next_offset = offset + len(comments)
    if len(comments) < limit and (comments or offset == 0):
        total = next_offset
    else:
        total = await comment_repo.count_comments(
            session,
            thread_id=thread.id,
            parent_comment_id=parent_comment_id,
            viewer=viewer,
        )
    has_more = next_offset < total

    # Replies to preview, for the comments that have any
    previews: dict[int, list[Comment]] = {}
    reply_totals: dict[int, int] = {}
    if parent_comment_id is None and reply_preview > 0:
        for reply, total_replies in await comment_repo.list_reply_previews(
            session,
            parent_comment_ids=[comment.id for comment in comments if comment.reply_count > 0],
            per_parent=reply_preview,
            viewer=viewer,
        ):
            previews.setdefault(reply.parent_comment_id, []).append(reply)
            reply_totals[reply.parent_comment_id] = total_replies

    await _attach_votes(
        session, viewer, comments + [reply for replies in previews.values() for reply in replies]
    )

    items = present_comments(comments, viewer, CommentTreeRead)
    for item in items:
        replies = previews.get(item.id)
        if not replies:
            continue
        item.replies = present_comments(replies, viewer, CommentTreeRead)
        item.replies_total = reply_totals[item.id]
        item.replies_has_more = len(replies) < item.replies_total
        # The rest load from the start (oldest first, as replies are listed), skipping the ones shown
        item.replies_next_offset = 0 if item.replies_has_more else None

    return PageResponse[CommentTreeRead](
        items=items,
        limit=limit,
        offset=offset,
        next_offset=next_offset if has_more else None,
        has_more=has_more,
        total=total,
    )


async def load_context(
    session: AsyncSession,
    *,
    thread: Thread | None,
    viewer: CommunityUser | None,
    comment_id: int,
    limit: int,
) -> CommentContextRead:
    """The chain from a comment's top-level comment down to it, and its first page of replies (oldest first, as replies
    are listed). Lets a widget show a comment that's deep in a thread or far down the list."""
    comment = await comment_repo.get_comment_by_id(session, comment_id)

    # The same answer whether the thread or the comment is missing, or the comment is in another thread
    if (
        not thread
        or thread.is_deleted
        or not comment
        or comment.thread_id != thread.id
        or not comment_repo.is_shown_in_thread(comment, viewer)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    # Nearest first from the repository; the top-level comment first here
    chain = list(reversed(await comment_repo.get_comment_ancestor_chain(session, comment=comment))) + [comment]

    total_replies = await comment_repo.count_comments(
        session,
        thread_id=thread.id,
        parent_comment_id=comment.id,
        viewer=viewer,
    )
    replies = await comment_repo.list_comments(
        session,
        thread_id=thread.id,
        parent_comment_id=comment.id,
        limit=limit,
        offset=0,
        sort="oldest",
        viewer=viewer,
    )

    await _attach_votes(session, viewer, chain + replies)

    presented_chain = present_comments(chain, viewer, CommentTreeRead)

    # Built from the comment up: each ancestor holds only the next comment in the chain, and says it has more when it
    # does, from the start of its replies (the widget skips the one it already shows)
    node = presented_chain[-1]
    node.replies = present_comments(replies, viewer, CommentTreeRead)
    node.replies_next_offset = len(replies) if len(replies) < total_replies else None
    node.replies_has_more = len(replies) < total_replies
    node.replies_total = total_replies
    for ancestor in reversed(presented_chain[:-1]):
        # Direct replies only: reply_count counts every reply below a comment, at any depth
        direct_replies = await comment_repo.count_comments(
            session,
            thread_id=thread.id,
            parent_comment_id=ancestor.id,
            viewer=viewer,
        )
        ancestor.replies = [node]
        ancestor.replies_total = direct_replies
        ancestor.replies_has_more = direct_replies > 1
        ancestor.replies_next_offset = 0 if ancestor.replies_has_more else None
        node = ancestor

    return CommentContextRead(focused_comment_id=comment.id, root=node)


async def _require_parent(session: AsyncSession, thread: Thread, parent_comment_id: int) -> None:
    parent = await comment_repo.get_comment_by_id(session, parent_comment_id)

    if not parent or parent.status not in comment_repo.THREAD_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent comment not found",
        )

    if parent.thread_id != thread.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent comment belongs to a different thread",
        )


async def _attach_votes(session: AsyncSession, viewer: CommunityUser | None, comments: list[Comment]) -> None:
    if viewer is None or not comments:
        return
    votes = await vote_repo.list_votes_for_comments(
        session,
        comment_ids=[comment.id for comment in comments],
        community_user_id=viewer.id,
    )
    for comment in comments:
        comment.viewer_vote = votes.get(comment.id)
