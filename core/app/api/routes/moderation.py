# app/api/routes/moderation.py

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_moderator
from app.db.session import get_async_session
from app.models.community import Community
from app.models.community_user import CommunityUser
from app.schemas.embed import PageResponse, ThreadRead
from app.schemas.moderation import (
    BanRead,
    BanRequest,
    BatchRequest,
    BatchResult,
    CommentFilters,
    LockThreadRequest,
    ModerationActionRead,
    ModerationCommentRead,
    ReasonRequest,
    ReportedCommentRead,
    ResolveReportsRequest,
)
from app.services import moderation_service

# Every route needs a token whose host-signed role makes the caller staff (app.api.deps.require_moderator)
router = APIRouter(prefix="/moderation", tags=["moderation"])

Moderator = tuple[Community, CommunityUser]


def page(items, *, limit: int, offset: int, total: int):
    next_offset = offset + len(items)
    has_more = next_offset < total
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
        "total": total,
    }


@router.get("/reports", response_model=PageResponse[ReportedCommentRead])
async def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    items, total = await moderation_service.list_reported_comments(
        session, community=context[0], limit=limit, offset=offset
    )
    return page(
        [{"comment": comment, "reports": reports} for comment, reports in items],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.post("/comments/{comment_id}/reports/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_reports(
    comment_id: int,
    payload: ResolveReportsRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    await moderation_service.resolve_reports(
        session, community=context[0], moderator=context[1], comment_id=comment_id, new_status=payload.status
    )


@router.get("/comments", response_model=PageResponse[ModerationCommentRead])
async def search_comments(
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    q: str | None = Query(default=None, max_length=200),
    source: str | None = Query(default=None, max_length=255),
    client: str | None = Query(default=None, max_length=32),
    community_user_id: UUID | None = Query(default=None),
    thread_id: str | None = Query(default=None, max_length=512),
    since: AwareDatetime | None = Query(default=None),
    until: AwareDatetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    items, total = await moderation_service.search_comments(
        session,
        community=context[0],
        filters=CommentFilters(
            source=source,
            client=client,
            community_user_id=community_user_id,
            thread_id=thread_id,
            since=since,
            until=until,
        ),
        status_filter=status_filter,
        search=q,
        limit=limit,
        offset=offset,
    )
    return page(items, limit=limit, offset=offset, total=total)


@router.post("/comments/batch", response_model=BatchResult)
async def batch_comments(
    payload: BatchRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    matched, changed = await moderation_service.batch_comments(
        session,
        community=context[0],
        moderator=context[1],
        filters=payload,
        action=payload.action,
        reason=payload.reason,
        dry_run=payload.dry_run,
    )
    return BatchResult(matched=matched, changed=changed)


@router.post("/comments/{comment_id}/hide", response_model=ModerationCommentRead)
async def hide_comment(
    comment_id: int,
    payload: ReasonRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await moderation_service.hide_comment(
        session, community=context[0], moderator=context[1], comment_id=comment_id, reason=payload.reason
    )


@router.post("/comments/{comment_id}/restore", response_model=ModerationCommentRead)
async def restore_comment(
    comment_id: int,
    payload: ReasonRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await moderation_service.restore_comment(
        session, community=context[0], moderator=context[1], comment_id=comment_id, reason=payload.reason
    )


@router.get("/bans", response_model=PageResponse[BanRead])
async def list_bans(
    active: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    items, total = await moderation_service.list_bans(
        session, community=context[0], active_only=active, limit=limit, offset=offset
    )
    return page(items, limit=limit, offset=offset, total=total)


@router.post("/bans", response_model=BanRead)
async def ban_user(
    payload: BanRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await moderation_service.ban_user(
        session,
        community=context[0],
        moderator=context[1],
        community_user_id=payload.community_user_id,
        reason=payload.reason,
        expires_at=payload.expires_at,
    )


@router.post("/bans/{ban_id}/lift", response_model=BanRead)
async def lift_ban(
    ban_id: int,
    payload: ReasonRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await moderation_service.lift_ban(
        session, community=context[0], moderator=context[1], ban_id=ban_id, reason=payload.reason
    )


@router.post("/threads/lock", response_model=ThreadRead)
async def lock_thread(
    payload: LockThreadRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await moderation_service.set_thread_locked(
        session,
        community=context[0],
        moderator=context[1],
        unique_id=payload.thread_id,
        locked=payload.locked,
        reason=payload.reason,
    )


@router.get("/actions", response_model=PageResponse[ModerationActionRead])
async def list_actions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    items, total = await moderation_service.list_actions(session, community=context[0], limit=limit, offset=offset)
    return page(items, limit=limit, offset=offset, total=total)
