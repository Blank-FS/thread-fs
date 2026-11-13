# app/api/routes/embed.py

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_optional_current_community_user,
    require_valid_embed_context,
)
from app.db.session import get_async_session
from app.models.community import Community
from app.models.community_user import CommunityUser
from app.api.rate_limits import (
    limit_create_comment,
    limit_delete_comment,
    limit_edit_comment,
    limit_read_comments,
    limit_report_comment,
    limit_vote_comment,
)
from app.schemas.embed import (
    CommentContextRead,
    CommentTreeRead,
    CommentCreateRequest,
    CommentRead,
    CommentWithThreadRead,
    EmbedCommunityConfigRead,
    EmbedMeRead,
    GifConfigRead,
    ReportRequest,
    ResolveThreadRequest,
    ResolveThreadResponse,
    VoteRequest,
    CommentUpdateRequest,
    PageResponse,
)
from app.services import (
    thread_service,
    comment_service,
    vote_service,
    comment_mutation_service,
    reason_service,
    report_service,
)

import app.repositories.thread as thread_repo
import app.repositories.comment as comment_repo
import app.repositories.comment_vote as vote_repo
import app.repositories.community_user as community_user_repo


router = APIRouter(prefix="/embed", tags=["embed"])


@router.get("/config", response_model=EmbedCommunityConfigRead)
async def get_embed_config(
    session: AsyncSession = Depends(get_async_session),
    community: Community = Depends(require_valid_embed_context),
):
    return EmbedCommunityConfigRead(
        community_id=community.id,
        name=community.name,
        slug=community.slug,
        allow_anonymous_read=community.allow_anonymous_read,
        allow_anonymous_comment=community.allow_anonymous_comment,
        report_reasons=await reason_service.list_reasons(session, community.id),
        rules_url=community.rules_url,
        gifs=GifConfigRead(app_key=community.klipy_app_key) if community.klipy_app_key else None,
        image_hosts=community.image_hosts or [],
    )


@router.get("/me", response_model=EmbedMeRead)
async def get_embed_me(
    community: Community = Depends(require_valid_embed_context),
    community_user: CommunityUser = Depends(get_optional_current_community_user),
):
    if not community_user:
        return EmbedMeRead(
            authenticated=False,
            community_user_id=None,
            identity_provider=None,
            external_user_id=None,
            display_name=None,
            avatar_url=None,
            threadfs_user_id=None,
        )

    return EmbedMeRead(
        authenticated=True,
        community_user_id=community_user.id,
        identity_provider=community_user.identity_provider,
        external_user_id=community_user.external_user_id,
        display_name=community_user.display_name,
        avatar_url=community_user.avatar_url,
        avatar_frame_url=community_user.avatar_frame_url,
        threadfs_user_id=community_user.threadfs_user_id,
        staff_role=community_user.staff_role,
    )


@router.post("/threads/resolve", response_model=ResolveThreadResponse)
async def resolve_embed_thread(
    payload: ResolveThreadRequest,
    session: AsyncSession = Depends(get_async_session),
    community: Community = Depends(require_valid_embed_context),
):
    thread = await thread_service.resolve_thread(
        session,
        community=community,
        thread_id=payload.thread_id,
    )

    return ResolveThreadResponse(
        exists=thread is not None,
        thread=thread,
    )


@router.get("/comments", response_model=PageResponse[CommentRead])
async def list_embed_comments(
    thread_id: str = Query(min_length=1, max_length=512),
    parent_comment_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: Literal["latest", "oldest", "top"] | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    community: Community = Depends(limit_read_comments),
    community_user: CommunityUser | None = Depends(get_optional_current_community_user),
):
    if not community.allow_anonymous_read and not community_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to read comments",
        )

    thread = await thread_repo.get_thread_by_unique_id(
        session,
        community_id=community.id,
        unique_id=thread_id,
    )

    # Important: read should not create a thread.
    if not thread:
        return PageResponse[CommentRead](
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
        parent_comment = await comment_repo.get_comment_by_id(
            session,
            parent_comment_id,
        )

        if not parent_comment or parent_comment.status not in comment_repo.THREAD_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found",
            )

        if parent_comment.thread_id != thread.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent comment belongs to a different thread",
            )

    effective_sort = sort or ("oldest" if parent_comment_id is not None else "latest")

    total = await comment_repo.count_comments(
        session,
        thread_id=thread.id,
        parent_comment_id=parent_comment_id,
    )

    comments = await comment_repo.list_comments(
        session,
        thread_id=thread.id,
        parent_comment_id=parent_comment_id,
        limit=limit,
        offset=offset,
        sort=effective_sort,
    )

    if community_user and comments:
        vote_map = await vote_repo.list_votes_for_comments(
            session,
            comment_ids=[comment.id for comment in comments],
            community_user_id=community_user.id,
        )
        for comment in comments:
            comment.viewer_vote = vote_map.get(comment.id)

    next_offset = offset + len(comments)
    has_more = next_offset < total

    return PageResponse[CommentRead](
        items=comment_service.present_comments(comments, community_user),
        limit=limit,
        offset=offset,
        next_offset=next_offset if has_more else None,
        has_more=has_more,
        total=total,
    )


@router.get("/comments/{comment_id}/context", response_model=CommentContextRead)
async def get_embed_comment_context(
    comment_id: int,
    thread_id: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    community: Community = Depends(limit_read_comments),
    community_user: CommunityUser | None = Depends(get_optional_current_community_user),
):
    """A link to one comment: the chain from its top-level comment down to it, and its first page of replies (oldest
    first, as replies are listed). Lets a widget show a comment that's deep in a thread or far down the list."""
    if not community.allow_anonymous_read and not community_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to read comments",
        )

    thread = await thread_repo.get_thread_by_unique_id(
        session,
        community_id=community.id,
        unique_id=thread_id,
    )
    comment = await comment_repo.get_comment_by_id(session, comment_id)

    # The same answer whether the thread or the comment is missing, or the comment is in another thread
    if (
        not thread
        or thread.is_deleted
        or not comment
        or comment.thread_id != thread.id
        or comment.status not in comment_repo.THREAD_STATUSES
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
    )
    replies = await comment_repo.list_comments(
        session,
        thread_id=thread.id,
        parent_comment_id=comment.id,
        limit=limit,
        offset=0,
        sort="oldest",
    )

    if community_user:
        vote_map = await vote_repo.list_votes_for_comments(
            session,
            comment_ids=[c.id for c in chain + replies],
            community_user_id=community_user.id,
        )
        for c in chain + replies:
            c.viewer_vote = vote_map.get(c.id)

    presented_chain = comment_service.present_comments(chain, community_user)
    presented_replies = comment_service.present_comments(replies, community_user)

    # Built from the comment up: each ancestor holds only the next comment in the chain, and says it has more when it
    # does, from the start of its replies (the widget skips the one it already shows)
    node = CommentTreeRead(
        **presented_chain[-1].model_dump(),
        replies=[CommentTreeRead(**reply.model_dump()) for reply in presented_replies],
        replies_next_offset=len(replies) if len(replies) < total_replies else None,
        replies_has_more=len(replies) < total_replies,
        replies_total=total_replies,
    )
    for ancestor in reversed(presented_chain[:-1]):
        # Direct replies only: reply_count counts every reply below a comment, at any depth
        direct_replies = await comment_repo.count_comments(
            session,
            thread_id=thread.id,
            parent_comment_id=ancestor.id,
        )
        has_more = direct_replies > 1
        node = CommentTreeRead(
            **ancestor.model_dump(),
            replies=[node],
            replies_next_offset=0 if has_more else None,
            replies_has_more=has_more,
            replies_total=direct_replies,
        )

    return CommentContextRead(focused_comment_id=comment.id, root=node)


@router.get("/comments/mine", response_model=PageResponse[CommentWithThreadRead])
async def list_my_embed_comments(
    external_user_id: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    community: Community = Depends(limit_read_comments),
    viewer: CommunityUser | None = Depends(get_optional_current_community_user),
):
    # With external_user_id: list that user's public comments (subject to
    # the community's anonymous-read policy, same as thread comments).
    # Without it: list the authenticated requester's own comments.
    if external_user_id is not None:
        if not community.allow_anonymous_read and not viewer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to read comments",
            )

        target_user = await community_user_repo.get_by_external_id(
            session,
            community_id=community.id,
            external_user_id=external_user_id,
        )

        if not target_user:
            return PageResponse[CommentWithThreadRead](
                items=[],
                limit=limit,
                offset=offset,
                next_offset=None,
                has_more=False,
                total=0,
            )
    else:
        if not viewer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to read your comments",
            )

        target_user = viewer

    # Removed comments show only to their author, never on someone else's view of a profile
    own_comments = viewer is not None and viewer.id == target_user.id

    total = await comment_repo.count_comments_by_community_user(
        session,
        community_user_id=target_user.id,
        community_id=community.id,
        include_hidden=own_comments,
    )

    comments = await comment_repo.list_comments_by_community_user(
        session,
        community_user_id=target_user.id,
        community_id=community.id,
        limit=limit,
        offset=offset,
        include_hidden=own_comments,
    )

    if viewer and comments:
        vote_map = await vote_repo.list_votes_for_comments(
            session,
            comment_ids=[comment.id for comment in comments],
            community_user_id=viewer.id,
        )
        for comment in comments:
            comment.viewer_vote = vote_map.get(comment.id)

    next_offset = offset + len(comments)
    has_more = next_offset < total

    return PageResponse[CommentWithThreadRead](
        items=comments,
        limit=limit,
        offset=offset,
        next_offset=next_offset if has_more else None,
        has_more=has_more,
        total=total,
    )


@router.post("/comments", response_model=CommentRead)
async def create_embed_comment(
    payload: CommentCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    limited_context: tuple[Community, CommunityUser] = Depends(limit_create_comment),
):
    community, community_user = limited_context
    user_agent = request.headers.get("user-agent")

    return await comment_service.create_embed_comment(
        session,
        community=community,
        community_user=community_user,
        external_thread_id=payload.thread_id,
        title=payload.title,
        source_url=payload.source_url,
        content=payload.content,
        gif=payload.gif,
        image=payload.image,
        parent_comment_id=payload.parent_comment_id,
        user_agent=user_agent,
        source=payload.source,
        client=payload.client,
    )


@router.post("/comments/{comment_id}/reports", status_code=status.HTTP_204_NO_CONTENT)
async def report_embed_comment(
    comment_id: int,
    payload: ReportRequest,
    session: AsyncSession = Depends(get_async_session),
    limited_context: tuple[Community, CommunityUser] = Depends(limit_report_comment),
):
    community, community_user = limited_context

    await report_service.report_comment(
        session,
        community=community,
        community_user=community_user,
        comment_id=comment_id,
        reason=payload.reason,
        details=payload.details,
    )


@router.post("/comments/{comment_id}/votes", response_model=CommentRead)
async def vote_embed_comment(
    comment_id: int,
    payload: VoteRequest,
    session: AsyncSession = Depends(get_async_session),
    limited_context: tuple[Community, CommunityUser] = Depends(limit_vote_comment),
):
    community, community_user = limited_context

    return await vote_service.vote_on_comment(
        session,
        community=community,
        community_user=community_user,
        comment_id=comment_id,
        value=payload.value,
    )


@router.patch("/comments/{comment_id}", response_model=CommentRead)
async def update_embed_comment(
    comment_id: int,
    payload: CommentUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    limited_context: tuple[Community, CommunityUser] = Depends(limit_edit_comment),
):
    community, community_user = limited_context

    updated = await comment_mutation_service.edit_own_comment(
        session,
        community=community,
        community_user=community_user,
        comment_id=comment_id,
        content=payload.content,
        gif=payload.gif,
        replace_gif="gif" in payload.model_fields_set,
        image=payload.image,
        replace_image="image" in payload.model_fields_set,
    )

    return updated


@router.delete("/comments/{comment_id}", response_model=CommentRead)
async def delete_embed_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_async_session),
    limited_context: tuple[Community, CommunityUser] = Depends(limit_delete_comment),
):
    community, community_user = limited_context

    deleted = await comment_mutation_service.delete_own_comment(
        session,
        community=community,
        community_user=community_user,
        comment_id=comment_id,
    )

    return deleted
