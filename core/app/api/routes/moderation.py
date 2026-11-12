# app/api/routes/moderation.py

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_moderator
from app.db.session import get_async_session
from app.models.community import Community
from app.models.community_user import CommunityUser
from app.schemas.embed import PageResponse, ReasonRead, ThreadRead
from app.schemas.moderation import (
    BanRead,
    BanRequest,
    BatchRequest,
    AdminOverviewRead,
    BatchResult,
    ClearImagesRequest,
    LimitsRequest,
    RulesRequest,
    GifsRequest,
    UndoBatchResult,
    CommentFilters,
    LockThreadRequest,
    ModerationActionRead,
    ModerationCommentRead,
    ModerationUserDetailRead,
    ModerationUserRead,
    ReasonRequest,
    ReasonsRequest,
    RemoveRequest,
    ReportedCommentRead,
    ResolveReportsRequest,
    UserNoteRead,
    UserNoteRequest,
)
from app.services import moderation_service, reason_service
from app.services.reason_service import Reason

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
    status_filter: Literal["open", "closed"] = Query(default="open", alias="status"),
    reason: str | None = Query(default=None, max_length=64),
    sort: Literal["newest", "oldest", "most_reported"] = Query(default="newest"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    items, total = await moderation_service.list_reported_comments(
        session,
        community=context[0],
        report_status=status_filter,
        reason=reason,
        sort=sort,
        limit=limit,
        offset=offset,
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


@router.post("/comments/{comment_id}/reports/reopen", status_code=status.HTTP_204_NO_CONTENT)
async def reopen_reports(
    comment_id: int,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    await moderation_service.reopen_reports(
        session, community=context[0], moderator=context[1], comment_id=comment_id
    )


@router.get("/comments", response_model=PageResponse[ModerationCommentRead])
async def search_comments(
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    q: str | None = Query(default=None, max_length=200),
    source: str | None = Query(default=None, max_length=255),
    client: str | None = Query(default=None, max_length=32),
    community_user_id: UUID | None = Query(default=None),
    thread_id: str | None = Query(default=None, max_length=512),
    removal_reason: str | None = Query(default=None, max_length=128),
    without_removal_reason: bool | None = Query(default=None),
    removed_by: UUID | None = Query(default=None),
    since: AwareDatetime | None = Query(default=None),
    until: AwareDatetime | None = Query(default=None),
    sort: Literal["newest", "oldest", "changed", "most_downvoted"] = Query(default="newest"),
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
            removal_reason=removal_reason,
            without_removal_reason=without_removal_reason,
            removed_by=removed_by,
            since=since,
            until=until,
        ),
        status_filter=status_filter,
        search=q,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return page(items, limit=limit, offset=offset, total=total)


@router.post("/comments/batch", response_model=BatchResult, response_model_exclude_none=True)
async def batch_comments(
    payload: BatchRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    matched, changed, refused = await moderation_service.batch_comments(
        session,
        community=context[0],
        moderator=context[1],
        filters=payload,
        action=payload.action,
        reason_key=payload.reason_key,
        reason_detail=payload.reason_detail,
        note=payload.note,
        dry_run=payload.dry_run,
    )
    return BatchResult(matched=matched, changed=changed, refused=refused)


@router.get("/admin", response_model=AdminOverviewRead)
async def admin_overview(
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_admin),
):
    return await moderation_service.get_admin_overview(session, community=context[0])


@router.put("/admin/limits", response_model=AdminOverviewRead)
async def update_limits(
    payload: LimitsRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_admin),
):
    await moderation_service.update_limits(
        session,
        community=context[0],
        moderator=context[1],
        max_batch_size=payload.max_batch_size,
        max_daily_batch_changes=payload.max_daily_batch_changes,
    )
    return await moderation_service.get_admin_overview(session, community=context[0])


@router.put("/admin/rules", response_model=AdminOverviewRead)
async def update_rules(
    payload: RulesRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_admin),
):
    await moderation_service.update_rules_url(
        session,
        community=context[0],
        moderator=context[1],
        rules_url=payload.rules_url,
    )
    return await moderation_service.get_admin_overview(session, community=context[0])


@router.put("/admin/gifs", response_model=AdminOverviewRead)
async def update_gifs(
    payload: GifsRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_admin),
):
    await moderation_service.update_klipy_app_key(
        session,
        community=context[0],
        moderator=context[1],
        klipy_app_key=payload.klipy_app_key,
    )
    return await moderation_service.get_admin_overview(session, community=context[0])


@router.post("/batches/{batch_id}/undo", response_model=UndoBatchResult)
async def undo_batch(
    batch_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_admin),
):
    changed, skipped = await moderation_service.undo_batch(
        session, community=context[0], moderator=context[1], batch_id=batch_id
    )
    return UndoBatchResult(changed=changed, skipped=skipped)


@router.post("/comments/{comment_id}/hide", response_model=ModerationCommentRead)
async def hide_comment(
    comment_id: int,
    payload: RemoveRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await moderation_service.hide_comment(
        session,
        community=context[0],
        moderator=context[1],
        comment_id=comment_id,
        reason_key=payload.reason_key,
        reason_detail=payload.reason_detail,
        note=payload.note,
        ban=payload.ban,
        ban_expires_at=payload.ban_expires_at,
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
    status_filter: Literal["active", "expired", "lifted", "all"] = Query(default="active", alias="status"),
    length: Literal["permanent", "temporary"] | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    banned_by: UUID | None = Query(default=None),
    sort: Literal["newest", "oldest", "ending_soon"] = Query(default="newest"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    items, total = await moderation_service.list_bans(
        session,
        community=context[0],
        ban_status=status_filter,
        length=length,
        search=q,
        banned_by=banned_by,
        sort=sort,
        limit=limit,
        offset=offset,
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


@router.get("/users", response_model=PageResponse[ModerationUserRead])
async def search_users(
    q: str | None = Query(default=None, max_length=200),
    only: Literal["banned", "removed", "reported"] | None = Query(default=None),
    sort: Literal["name", "newest", "most_comments", "most_removed", "most_reported"] = Query(default="name"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    items, total = await moderation_service.search_users(
        session, community=context[0], search=q, only=only, sort=sort, limit=limit, offset=offset
    )
    return page(items, limit=limit, offset=offset, total=total)


@router.post("/users/clear-images", status_code=status.HTTP_204_NO_CONTENT)
async def clear_user_images(
    payload: ClearImagesRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    """For the host to call when it removes a user's avatar or frame, so comments stop showing it at once."""
    await moderation_service.clear_user_images(
        session,
        community=context[0],
        moderator=context[1],
        external_user_id=payload.external_user_id,
        avatar=payload.avatar,
        frame=payload.frame,
        reason=payload.reason,
    )


@router.get("/users/{community_user_id}", response_model=ModerationUserDetailRead)
async def get_user(
    community_user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await moderation_service.get_user(session, community=context[0], community_user_id=community_user_id)


@router.post("/users/{community_user_id}/notes", response_model=UserNoteRead)
async def add_note(
    community_user_id: UUID,
    payload: UserNoteRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await moderation_service.add_note(
        session,
        community=context[0],
        moderator=context[1],
        community_user_id=community_user_id,
        body=payload.body,
    )


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    await moderation_service.delete_note(session, community=context[0], note_id=note_id)


@router.get("/reasons", response_model=list[ReasonRead])
async def list_reasons(
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    return await reason_service.list_reasons(session, context[0].id)


@router.put("/reasons", response_model=list[ReasonRead])
async def replace_reasons(
    payload: ReasonsRequest,
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_admin),
):
    return await reason_service.replace_reasons(
        session,
        context[0].id,
        [Reason(reason.key, reason.label) for reason in payload.reasons],
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
    action: str | None = Query(default=None, max_length=64),
    moderator: UUID | None = Query(default=None),
    target: UUID | None = Query(default=None),
    since: AwareDatetime | None = Query(default=None),
    until: AwareDatetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    context: Moderator = Depends(require_moderator),
):
    items, total = await moderation_service.list_actions(
        session,
        community=context[0],
        action=action,
        moderator=moderator,
        target=target,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return page(items, limit=limit, offset=offset, total=total)
