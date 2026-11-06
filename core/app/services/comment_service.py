# app/services/comment_service.py

from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.community_user import CommunityUser
from app.repositories import comment as comment_repo
from app.repositories import thread as thread_repo
from app.core.sanitize import sanitize_comment_markdown
from app.core.origin import normalize_origin
from app.repositories.community import is_origin_allowed_for_community
from app.schemas.embed import CommentRead
from app.services import moderation_service


async def get_or_create_thread_for_comment(
    session: AsyncSession,
    *,
    community: Community,
    external_thread_id: str,
    title: str | None,
    source_url: str | None,
    trusted: bool = False,
    may_create: bool = True,
):
    """Finds or creates a thread. Only trusted details change an existing one, so a commenter can't repoint it."""
    existing = await thread_repo.get_thread_by_unique_id(
        session,
        community_id=community.id,
        unique_id=external_thread_id,
    )

    if existing:
        changed = False

        if trusted and title and existing.title != title:
            existing.title = title
            changed = True

        if trusted and source_url and existing.source_url != source_url:
            existing.source_url = source_url
            changed = True

        if changed:
            await session.flush()

        return existing

    if not may_create:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    try:
        thread = await thread_repo.create_thread(
            session,
            community_id=community.id,
            unique_id=external_thread_id,
            title=title,
            source_url=source_url,
        )

        await session.flush()
        return thread

    except IntegrityError:
        await session.rollback()

        existing = await thread_repo.get_thread_by_unique_id(
            session,
            community_id=community.id,
            unique_id=external_thread_id,
        )

        if existing is None:
            raise

        return existing


async def _source_url_on_community(
    session: AsyncSession,
    community: Community,
    source_url: str | None,
) -> str | None:
    """A browser-sent link, kept only if it points at one of the community's own sites."""
    if not source_url:
        return None

    try:
        origin = normalize_origin(source_url)
    except ValueError:
        return None

    if not origin.startswith(("https://", "http://")):
        return None

    allowed = await is_origin_allowed_for_community(session, community_id=community.id, origin=origin)
    return source_url if allowed else None


async def create_embed_comment(
    session: AsyncSession,
    *,
    community: Community,
    community_user: CommunityUser,
    external_thread_id: str,
    title: str | None,
    source_url: str | None,
    content: str,
    parent_comment_id: int | None,
    ip_hash: str | None = None,
    user_agent: str | None = None,
    source: str | None = None,
    client: str | None = None,
):
    await moderation_service.require_not_banned(
        session,
        community_id=community.id,
        community_user_id=community_user.id,
    )

    claim = community_user.thread_claim
    vouched = claim is not None and claim.id == external_thread_id

    if community_user.signed_threads:
        title, source_url = (claim.title, claim.url) if vouched else (None, None)
    else:
        source_url = await _source_url_on_community(session, community, source_url)

    thread = await get_or_create_thread_for_comment(
        session,
        community=community,
        external_thread_id=external_thread_id,
        title=title,
        source_url=source_url,
        trusted=vouched,
        may_create=vouched or not community_user.signed_threads,
    )

    if thread.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    if thread.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Thread is locked",
        )

    parent_comment = None
    ancestors = []

    if parent_comment_id is not None:
        parent_comment = await comment_repo.get_comment_by_id(
            session,
            parent_comment_id,
        )

        if not parent_comment or parent_comment.status != "visible":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found",
            )

        if parent_comment.thread_id != thread.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent comment belongs to a different thread",
            )

        ancestors = await comment_repo.get_comment_ancestor_chain(
            session,
            comment=parent_comment,
        )

    clean_content = sanitize_comment_markdown(content)

    comment = await comment_repo.create_comment(
        session,
        thread_id=thread.id,
        community_user_id=community_user.id,
        content=clean_content,
        parent_comment_id=parent_comment_id,
        ip_hash=ip_hash,
        user_agent=user_agent,
        source=source,
        client=client,
    )

    thread.comment_count += 1

    if parent_comment is not None:
        parent_comment.reply_count += 1

        for ancestor in ancestors:
            ancestor.reply_count += 1

    await session.commit()

    created = await comment_repo.get_comment_by_id(session, comment.id)

    if created is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load created comment",
        )

    return created


def present_comments(comments, viewer) -> list[CommentRead]:
    """Comments as a viewer may see them: one moderators removed keeps its place as an empty "[removed]", with its text
    and author withheld, unless the viewer wrote it. Works on copies, so nothing here can be saved back."""
    presented = [CommentRead.model_validate(comment) for comment in comments]

    for comment in presented:
        if comment.status == "hidden" and (
            viewer is None or comment.community_user_id != viewer.id
        ):
            comment.content = ""
            comment.removal_reason = None
            comment.removal_detail = None
            comment.community_user = None
            comment.community_user_id = None
            comment.upvote_count = 0
            comment.downvote_count = 0

    return presented
