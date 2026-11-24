# app/api/routes/embed.py

from collections.abc import Awaitable, Callable, Hashable
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic_core import to_json
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_optional_current_community_user,
    require_community_context,
    require_valid_embed_context,
)
from app.core.config import settings
from app.core.ttl_cache import TTLCache
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
    BootstrapRead,
    BootstrapRequest,
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
    ThreadRead,
    VoteRequest,
    CommentUpdateRequest,
    PageResponse,
    ReplyingToRead,
)
from app.services import (
    thread_service,
    comment_page_service,
    comment_service,
    vote_service,
    comment_mutation_service,
    report_service,
)
from app.services.community_context import CommunityContext

import app.repositories.thread as thread_repo
import app.repositories.comment as comment_repo
import app.repositories.comment_vote as vote_repo
import app.repositories.community_user as community_user_repo


router = APIRouter(prefix="/embed", tags=["embed"])


# Signed-out readers all see the same, so those of one thread share an answer for a few seconds, ready to send: what keeps
# a thread that everyone opens at once cheap. Signed-in viewers share the page within theirs (comment_page_service).
_signed_out_reads: TTLCache[bytes] = TTLCache(settings.READ_CACHE_SECONDS, max_entries=200)


async def _read(viewer: CommunityUser | None, key: Hashable, load: Callable[[], Awaitable[dict]]) -> Response:
    async def body() -> bytes:
        return to_json(await load())

    content = await body() if viewer else await _signed_out_reads.get(key, body)
    # Made from the response models already, so there's nothing for FastAPI to check again
    return Response(content, media_type="application/json")


def _config_read(context: CommunityContext) -> EmbedCommunityConfigRead:
    community = context.community
    return EmbedCommunityConfigRead(
        community_id=community.id,
        name=community.name,
        slug=community.slug,
        allow_anonymous_read=community.allow_anonymous_read,
        allow_anonymous_comment=community.allow_anonymous_comment,
        report_reasons=context.reasons,
        rules_url=community.rules_url,
        gifs=GifConfigRead(app_key=community.klipy_app_key) if community.klipy_app_key else None,
        image_hosts=community.image_hosts or [],
    )


def _me_read(community_user: CommunityUser | None) -> EmbedMeRead:
    if not community_user:
        return EmbedMeRead(authenticated=False)

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


@router.post("/bootstrap", response_model=BootstrapRead)
async def bootstrap_embed(
    payload: BootstrapRequest,
    session: AsyncSession = Depends(get_async_session),
    context: CommunityContext = Depends(require_community_context),
    community: Community = Depends(limit_read_comments),
    community_user: CommunityUser | None = Depends(get_optional_current_community_user),
):
    """Everything a widget needs to show a thread, in one request. A POST, so its address is always the same and browsers
    reuse the preflight from one thread to the next."""
    comment_page_service.require_may_read(community, community_user)

    reply_preview = community.reply_preview if payload.reply_preview is None else payload.reply_preview

    async def load() -> dict:
        thread = await thread_repo.get_thread_by_unique_id(
            session,
            community_id=community.id,
            unique_id=payload.thread_id,
        )

        # A linked comment that's gone, or never was (no id is past the column's), leaves the thread to show as usual
        linked = None
        if payload.comment_id is not None and 0 < payload.comment_id < 2**31:
            try:
                linked = await comment_page_service.load_context(
                    session,
                    thread=thread,
                    viewer=community_user,
                    comment_id=payload.comment_id,
                    limit=payload.limit,
                )
            except HTTPException as error:
                if error.status_code != status.HTTP_404_NOT_FOUND:
                    raise

        return {
            "config": _config_read(context),
            "me": _me_read(community_user),
            "thread": ThreadRead.model_validate(thread) if thread else None,
            "context": linked,
            "comments": await comment_page_service.page_for(
                session,
                thread=thread,
                viewer=community_user,
                parent_comment_id=None,
                limit=payload.limit,
                offset=0,
                sort=payload.sort,
                reply_preview=reply_preview,
            ),
        }

    key = ("bootstrap", community.id, payload.thread_id, payload.comment_id, payload.limit, payload.sort, reply_preview)
    return await _read(community_user, key, load)


@router.get("/config", response_model=EmbedCommunityConfigRead)
async def get_embed_config(context: CommunityContext = Depends(require_community_context)):
    return _config_read(context)


@router.get("/me", response_model=EmbedMeRead)
async def get_embed_me(
    community_user: CommunityUser | None = Depends(get_optional_current_community_user),
):
    return _me_read(community_user)


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


@router.get("/comments", response_model=PageResponse[CommentTreeRead])
async def list_embed_comments(
    thread_id: str = Query(min_length=1, max_length=512),
    parent_comment_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: Literal["latest", "oldest", "top"] | None = Query(default=None),
    # Top-level lists only: how many of each comment's direct replies come with it (0 for none, the replies loading
    # on request), the community's own setting when left out. The best first; the rest load from offset 0 as usual,
    # skipping the ones already shown.
    reply_preview: int | None = Query(default=None, ge=0, le=5),
    session: AsyncSession = Depends(get_async_session),
    community: Community = Depends(limit_read_comments),
    community_user: CommunityUser | None = Depends(get_optional_current_community_user),
):
    comment_page_service.require_may_read(community, community_user)

    previews = community.reply_preview if reply_preview is None else reply_preview

    async def load() -> dict:
        thread = await thread_repo.get_thread_by_unique_id(
            session,
            community_id=community.id,
            unique_id=thread_id,
        )
        return await comment_page_service.page_for(
            session,
            thread=thread,
            viewer=community_user,
            parent_comment_id=parent_comment_id,
            limit=limit,
            offset=offset,
            sort=sort,
            reply_preview=previews,
        )

    key = ("comments", community.id, thread_id, parent_comment_id, limit, offset, sort, previews)
    return await _read(community_user, key, load)


@router.get("/comments/{comment_id}/context", response_model=CommentContextRead)
async def get_embed_comment_context(
    comment_id: int,
    thread_id: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    community: Community = Depends(limit_read_comments),
    community_user: CommunityUser | None = Depends(get_optional_current_community_user),
):
    """A link to one comment (comment_page_service.load_context)."""
    comment_page_service.require_may_read(community, community_user)

    thread = await thread_repo.get_thread_by_unique_id(
        session,
        community_id=community.id,
        unique_id=thread_id,
    )
    return await comment_page_service.load_context(
        session,
        thread=thread,
        viewer=community_user,
        comment_id=comment_id,
        limit=limit,
    )


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

    # Who each reply answers ("replied to Mira"), from its parent, in one query
    parents = {
        parent.id: parent
        for parent in await comment_repo.get_comments_by_ids(
            session, [comment.parent_comment_id for comment in comments if comment.parent_comment_id]
        )
    }
    for comment in comments:
        parent = parents.get(comment.parent_comment_id) if comment.parent_comment_id else None
        if parent is None:
            comment.replying_to = None
            continue
        # A removed parent's author is withheld from everyone but that author, as in the thread
        shows_author = parent.status == "visible" or (
            parent.status == "hidden" and viewer is not None and parent.community_user_id == viewer.id
        )
        author = parent.community_user if shows_author else None
        comment.replying_to = ReplyingToRead(
            status=parent.status,
            display_name=author.display_name if author else None,
            external_user_id=author.external_user_id if author else None,
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

    (presented,) = comment_service.present_comments([deleted], community_user)
    return presented
