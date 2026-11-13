# app/services/moderation_service.py

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.common import utc_now
from app.models.comment import Comment
from app.models.community import Community
from app.models.community_allowed_origin import CommunityAllowedOrigin
from app.models.community_user import CommunityUser
from app.models.moderation import CommunityBan, ModerationAction, ModerationBatch, UserNote
from app.models.report import CommentReport
from app.models.thread import Thread
from app.schemas.moderation import CommentFilters
from app.services import reason_service


#=============== Bans ===============


# Everything a BanRead shows
# How far back the admin overview's staff activity goes
ACTIVITY_DAYS = 7

# Filtering the log by an action also finds the batches of it, which read as one line
BATCH_SUMMARIES = {
    "hide_comment": ["hide_comment", "hide_batch"],
    "restore_comment": ["restore_comment", "restore_batch"],
}

BAN_DETAILS = (
    selectinload(CommunityBan.community_user),
    selectinload(CommunityBan.banned_by),
    selectinload(CommunityBan.lifted_by),
)


def _active(now: datetime):
    return (
        CommunityBan.lifted_at.is_(None),
        or_(CommunityBan.expires_at.is_(None), CommunityBan.expires_at > now),
    )


async def get_active_ban(session: AsyncSession, *, community_id: UUID, community_user_id: UUID):
    result = await session.execute(
        select(CommunityBan)
        .where(
            CommunityBan.community_id == community_id,
            CommunityBan.community_user_id == community_user_id,
            *_active(utc_now()),
        )
        .limit(1)
    )
    return result.scalars().first()


async def require_not_banned(session: AsyncSession, *, community_id: UUID, community_user_id: UUID) -> None:
    ban = await get_active_ban(session, community_id=community_id, community_user_id=community_user_id)
    if ban:
        until = f" until {ban.expires_at.strftime('%b %d, %Y %H:%M UTC')}" if ban.expires_at else ""
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are banned from this community{until}",
        )


async def ban_user(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    community_user_id: UUID,
    reason: str | None,
    expires_at: datetime | None,
) -> CommunityBan:
    target = await _require_user(session, community, community_user_id)
    _require_can_ban(moderator, target)
    _require_future(expires_at)

    if await get_active_ban(session, community_id=community.id, community_user_id=community_user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already banned")

    ban = _add_ban(session, community, moderator, community_user_id, reason, expires_at)
    await session.commit()
    return await _load_ban(session, ban.id)


def _require_can_ban(moderator: CommunityUser, target: CommunityUser) -> None:
    """Staff are known by the role in their latest token, so one who hasn't visited since gaining it isn't protected yet."""
    if target.id == moderator.id:
        detail = "You can't ban yourself"
    elif target.last_staff_role == "admin":
        detail = "Admins can't be banned"
    elif target.last_staff_role == "moderator" and moderator.staff_role != "admin":
        detail = "Only admins can ban moderators"
    else:
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _require_future(expires_at: datetime | None) -> None:
    if expires_at is not None and expires_at <= utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A ban must expire in the future")


def _add_ban(
    session: AsyncSession,
    community: Community,
    moderator: CommunityUser,
    community_user_id: UUID,
    reason: str | None,
    expires_at: datetime | None,
) -> CommunityBan:
    ban = CommunityBan(
        community_id=community.id,
        community_user_id=community_user_id,
        banned_by_community_user_id=moderator.id,
        reason=reason,
        expires_at=expires_at,
    )
    session.add(ban)
    _log(session, community, moderator, "ban_user", target_community_user_id=community_user_id, reason=reason)
    return ban


async def _require_user(session: AsyncSession, community: Community, community_user_id: UUID) -> CommunityUser:
    user = await session.get(CommunityUser, community_user_id)
    if not user or user.community_id != community.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def clear_user_images(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    external_user_id: str,
    avatar: bool,
    frame: bool,
    reason: str | None,
) -> None:
    """
    Forgets the avatar or frame URL kept for a user, for when the host has taken the image down: comments stop showing
    it straight away, rather than at the user's next visit. The host stays the source, so their next token sets both
    again from its claims. Someone who has never used the community has nothing stored, which is fine.
    """
    result = await session.execute(
        select(CommunityUser).where(
            CommunityUser.community_id == community.id,
            CommunityUser.identity_provider == moderator.identity_provider,
            CommunityUser.external_user_id == external_user_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        return

    if avatar and user.avatar_url:
        user.avatar_url = None
        _log(session, community, moderator, "clear_avatar", target_community_user_id=user.id, reason=reason)
    if frame and user.avatar_frame_url:
        user.avatar_frame_url = None
        _log(session, community, moderator, "clear_avatar_frame", target_community_user_id=user.id, reason=reason)
    await session.commit()


async def lift_ban(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    ban_id: int,
    reason: str | None,
) -> CommunityBan:
    ban = await session.get(CommunityBan, ban_id)
    if not ban or ban.community_id != community.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ban not found")
    if ban.lifted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ban was already lifted")

    target = await _require_user(session, community, ban.community_user_id)
    if target.last_staff_role == "moderator" and moderator.staff_role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can lift a moderator's ban")

    ban.lifted_at = utc_now()
    ban.lifted_by_community_user_id = moderator.id
    _log(session, community, moderator, "unban_user", target_community_user_id=ban.community_user_id, reason=reason)
    await session.commit()
    return await _load_ban(session, ban_id)


async def _load_ban(session: AsyncSession, ban_id: int) -> CommunityBan:
    result = await session.execute(
        select(CommunityBan)
        .options(*BAN_DETAILS)
        .where(CommunityBan.id == ban_id)
        .execution_options(populate_existing=True)
    )
    return result.scalars().one()


async def list_bans(
    session: AsyncSession,
    *,
    community: Community,
    ban_status: str,
    length: str | None,
    search: str | None,
    banned_by: UUID | None,
    sort: str,
    limit: int,
    offset: int,
):
    now = utc_now()
    query = select(CommunityBan).where(CommunityBan.community_id == community.id)

    if ban_status == "active":
        query = query.where(*_active(now))
    elif ban_status == "expired":
        query = query.where(CommunityBan.lifted_at.is_(None), CommunityBan.expires_at <= now)
    elif ban_status == "lifted":
        query = query.where(CommunityBan.lifted_at.is_not(None))

    if length == "permanent":
        query = query.where(CommunityBan.expires_at.is_(None))
    elif length == "temporary":
        query = query.where(CommunityBan.expires_at.is_not(None))

    if banned_by:
        query = query.where(CommunityBan.banned_by_community_user_id == banned_by)

    if search:
        pattern = "%" + _escape_like(search) + "%"
        query = query.join(CommunityUser, CommunityUser.id == CommunityBan.community_user_id).where(
            or_(
                CommunityUser.display_name.ilike(pattern, escape="\\"),
                CommunityUser.external_user_id.ilike(pattern, escape="\\"),
            )
        )

    order = {
        "newest": (CommunityBan.created_at.desc(), CommunityBan.id.desc()),
        "oldest": (CommunityBan.created_at.asc(), CommunityBan.id.asc()),
        "ending_soon": (CommunityBan.expires_at.asc().nulls_last(), CommunityBan.id.desc()),
    }[sort]

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.options(*BAN_DETAILS).order_by(*order).limit(limit).offset(offset))
    return list(result.scalars().all()), int(total or 0)


#=============== Comments ===============


def _log(session: AsyncSession, community: Community, moderator: CommunityUser, action: str, **fields) -> None:
    session.add(
        ModerationAction(
            community_id=community.id,
            moderator_community_user_id=moderator.id,
            action=action,
            **fields,
        )
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _comments_query(community: Community, filters: CommentFilters, *, status_filter: str | None, search: str | None):
    query = select(Comment).join(Thread, Thread.id == Comment.thread_id).where(Thread.community_id == community.id)
    if status_filter:
        query = query.where(Comment.status == status_filter)
    if filters.source:
        query = query.where(Comment.source == filters.source)
    if filters.client:
        query = query.where(Comment.client == filters.client)
    if filters.community_user_id:
        query = query.where(Comment.community_user_id == filters.community_user_id)
    if filters.thread_id:
        query = query.where(Thread.unique_id == filters.thread_id)
    if filters.comment_ids:
        query = query.where(Comment.id.in_(filters.comment_ids))
    if filters.removal_reason:
        query = query.where(Comment.removal_reason == filters.removal_reason)
    if filters.without_removal_reason:
        query = query.where(Comment.removal_reason.is_(None))
    if filters.removed_by:
        query = query.where(
            Comment.id.in_(
                select(ModerationAction.comment_id).where(
                    ModerationAction.action == "hide_comment",
                    ModerationAction.moderator_community_user_id == filters.removed_by,
                )
            )
        )
    if filters.since:
        query = query.where(Comment.created_at >= filters.since)
    if filters.until:
        query = query.where(Comment.created_at <= filters.until)
    if search:
        pattern = "%" + _escape_like(search) + "%"
        query = query.where(Comment.content.ilike(pattern, escape="\\"))
    return query


async def search_comments(
    session: AsyncSession,
    *,
    community: Community,
    filters: CommentFilters,
    status_filter: str | None,
    search: str | None,
    sort: str,
    limit: int,
    offset: int,
):
    query = _comments_query(community, filters, status_filter=status_filter, search=search)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    order = {
        "newest": (Comment.created_at.desc(), Comment.id.desc()),
        "oldest": (Comment.created_at.asc(), Comment.id.asc()),
        "changed": (Comment.modified_at.desc(), Comment.id.desc()),
        "most_downvoted": (Comment.downvote_count.desc(), Comment.created_at.desc(), Comment.id.desc()),
    }[sort]
    result = await session.execute(
        query.options(selectinload(Comment.community_user), selectinload(Comment.thread))
        .order_by(*order)
        .limit(limit)
        .offset(offset)
    )
    comments = list(result.scalars().all())
    await _attach_context(session, comments)
    return comments, int(total or 0)


async def _attach_context(session: AsyncSession, comments: list[Comment]) -> None:
    await _attach_parents(session, comments)
    await _attach_removals(session, comments)


async def _attach_removals(session: AsyncSession, comments: list[Comment]) -> None:
    """Who removed each removed comment, when and why: the latest such entry in the log."""
    hidden_ids = [comment.id for comment in comments if comment.status == "hidden"]
    latest: dict[int, ModerationAction] = {}

    if hidden_ids:
        result = await session.execute(
            select(ModerationAction)
            .options(selectinload(ModerationAction.moderator))
            .where(ModerationAction.action == "hide_comment", ModerationAction.comment_id.in_(hidden_ids))
            .order_by(ModerationAction.created_at.asc(), ModerationAction.id.asc())
        )
        latest = {action.comment_id: action for action in result.scalars().all()}

    for comment in comments:
        comment.removal = latest.get(comment.id)


async def _attach_parents(session: AsyncSession, comments: list[Comment]) -> None:
    parent_ids = {comment.parent_comment_id for comment in comments if comment.parent_comment_id}
    if not parent_ids:
        return

    result = await session.execute(
        select(Comment).options(selectinload(Comment.community_user)).where(Comment.id.in_(parent_ids))
    )
    parents = {parent.id: parent for parent in result.scalars().all()}
    for comment in comments:
        comment.parent = parents.get(comment.parent_comment_id)


async def _load_comment(session: AsyncSession, comment_id: int) -> Comment:
    result = await session.execute(
        select(Comment)
        .options(selectinload(Comment.community_user), selectinload(Comment.thread))
        .where(Comment.id == comment_id)
        .execution_options(populate_existing=True)
    )
    comment = result.scalars().one()
    await _attach_context(session, [comment])
    return comment


def _log_reason(*parts: str | None) -> str | None:
    return ": ".join(part for part in parts if part) or None


async def _removal_label(session: AsyncSession, community: Community, reason_key: str | None) -> str | None:
    if not reason_key:
        return None
    return (await reason_service.require_reason(session, community.id, reason_key)).label


def _removal_detail(reason_key: str | None, detail: str | None) -> str | None:
    if reason_key != reason_service.OTHER_REASON:
        return None

    detail = detail.strip() if detail else None
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Tell the author why this comment was removed",
        )
    return detail


async def _comment_in_community(session: AsyncSession, community: Community, comment_id: int) -> Comment:
    result = await session.execute(
        select(Comment)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Comment.id == comment_id, Thread.community_id == community.id)
    )
    comment = result.scalars().first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


async def _resolve_open_reports(
    session: AsyncSession,
    moderator: CommunityUser,
    comment_ids: list[int],
    new_status: str,
) -> int:
    result = await session.execute(
        update(CommentReport)
        .where(CommentReport.comment_id.in_(comment_ids), CommentReport.status == "open")
        .values(status=new_status, resolved_at=utc_now(), resolved_by_community_user_id=moderator.id)
    )
    return result.rowcount


async def hide_comment(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    comment_id: int,
    reason_key: str | None,
    note: str | None,
    reason_detail: str | None = None,
    ban: bool = False,
    ban_expires_at: datetime | None = None,
) -> Comment:
    comment = await _comment_in_community(session, community, comment_id)
    if comment.status != "visible":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Comment isn't visible")

    label = await _removal_label(session, community, reason_key)
    detail = _removal_detail(reason_key, reason_detail)
    reason = _log_reason(label, detail, note)

    if ban:
        _require_can_ban(moderator, await _require_user(session, community, comment.community_user_id))
        _require_future(ban_expires_at)
        # Someone already banned stays on the ban they have
        if not await get_active_ban(session, community_id=community.id, community_user_id=comment.community_user_id):
            _add_ban(session, community, moderator, comment.community_user_id, reason, ban_expires_at)

    comment.status = "hidden"
    comment.removal_reason = label
    comment.removal_detail = detail
    comment.modified_at = utc_now()
    _log(
        session,
        community,
        moderator,
        "hide_comment",
        comment_id=comment.id,
        thread_id=comment.thread_id,
        target_community_user_id=comment.community_user_id,
        reason=reason,
    )
    await _resolve_open_reports(session, moderator, [comment.id], "resolved")
    await session.commit()
    return await _load_comment(session, comment.id)


async def restore_comment(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    comment_id: int,
    reason: str | None,
) -> Comment:
    comment = await _comment_in_community(session, community, comment_id)
    if comment.status != "hidden":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Comment isn't hidden")

    comment.status = "visible"
    comment.removal_reason = None
    comment.removal_detail = None
    comment.modified_at = utc_now()
    _log(
        session,
        community,
        moderator,
        "restore_comment",
        comment_id=comment.id,
        thread_id=comment.thread_id,
        target_community_user_id=comment.community_user_id,
        reason=reason,
    )
    await session.commit()
    return await _load_comment(session, comment.id)


async def batch_comments(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    filters: CommentFilters,
    action: str,
    reason_key: str | None,
    note: str | None,
    dry_run: bool,
    reason_detail: str | None = None,
) -> tuple[int, int, str | None]:
    """Hides or restores everything matching the filters: the cleanup for a site or user gone wrong. Every comment gets
    its own log entry, so a batch can be reviewed, and an admin can undo it. A dry run says if it would be refused."""
    from_status, to_status = ("visible", "hidden") if action == "hide" else ("hidden", "visible")
    result = await session.execute(_comments_query(community, filters, status_filter=from_status, search=None))
    comments = list(result.scalars().all())

    counted = await _counts_toward_limit(session, community, moderator, filters, action)
    refused = await _batch_refusal(session, community, moderator, len(comments), counted)
    if dry_run or not comments:
        return len(comments), 0, refused
    if refused:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=refused)

    label = await _removal_label(session, community, reason_key) if action == "hide" else None
    detail = _removal_detail(reason_key, reason_detail) if action == "hide" else None
    reason = _log_reason(label, detail, note)

    batch = ModerationBatch(
        community_id=community.id,
        moderator_community_user_id=moderator.id,
        action=action,
        comment_count=len(comments),
        counts_toward_limit=counted,
    )
    session.add(batch)
    await session.flush()

    now = utc_now()
    for comment in comments:
        previous_reason, previous_detail = comment.removal_reason, comment.removal_detail
        comment.status = to_status
        comment.removal_reason = label
        comment.removal_detail = detail
        comment.modified_at = now
        _log(
            session,
            community,
            moderator,
            "hide_comment" if action == "hide" else "restore_comment",
            comment_id=comment.id,
            thread_id=comment.thread_id,
            target_community_user_id=comment.community_user_id,
            reason=reason,
            batch_id=batch.id,
            previous_removal_reason=previous_reason,
            previous_removal_detail=previous_detail,
        )
    _log(session, community, moderator, f"{action}_batch", batch_id=batch.id, reason=reason)
    if action == "hide":
        await _resolve_open_reports(session, moderator, [comment.id for comment in comments], "resolved")
    await session.commit()
    return len(comments), len(comments), None


async def _counts_toward_limit(
    session: AsyncSession,
    community: Community,
    moderator: CommunityUser,
    filters: CommentFilters,
    action: str,
) -> bool:
    """Admins have no limit. Clearing out one regular user is the everyday cleanup for a spammer, and can't reach far."""
    if moderator.staff_role == "admin":
        return False
    if action == "hide" and filters.community_user_id:
        target = await session.get(CommunityUser, filters.community_user_id)
        return target is None or target.community_id != community.id or target.last_staff_role is not None
    return True


async def _batch_refusal(
    session: AsyncSession,
    community: Community,
    moderator: CommunityUser,
    count: int,
    counted: bool,
) -> str | None:
    if not counted or not count:
        return None
    if count > community.max_batch_size:
        return f"This would change {count} comments. Moderators can change up to {community.max_batch_size} at once"

    since = utc_now() - timedelta(days=1)
    used = await session.scalar(
        select(func.coalesce(func.sum(ModerationBatch.comment_count), 0)).where(
            ModerationBatch.moderator_community_user_id == moderator.id,
            ModerationBatch.counts_toward_limit.is_(True),
            ModerationBatch.created_at >= since,
        )
    )
    left = max(community.max_daily_batch_changes - int(used or 0), 0)
    if count > left:
        return (
            f"This would change {count} comments, and moderators can change "
            f"{community.max_daily_batch_changes} a day in bulk. You have {left} left"
        )
    return None


async def undo_batch(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    batch_id: UUID,
) -> tuple[int, int]:
    """Puts back exactly what a batch changed, reasons included. A comment that's changed since stays as it is."""
    batch = await session.get(ModerationBatch, batch_id)
    if not batch or batch.community_id != community.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    if batch.undone_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Batch was already undone")

    entries = list(
        (
            await session.execute(
                select(ModerationAction)
                .options(selectinload(ModerationAction.comment))
                .where(ModerationAction.batch_id == batch.id, ModerationAction.comment_id.is_not(None))
            )
        )
        .scalars()
        .all()
    )
    latest = dict(
        (
            await session.execute(
                select(ModerationAction.comment_id, func.max(ModerationAction.id))
                .where(
                    ModerationAction.comment_id.in_([entry.comment_id for entry in entries]),
                    ModerationAction.action.in_(["hide_comment", "restore_comment"]),
                )
                .group_by(ModerationAction.comment_id)
            )
        ).all()
    )

    was_hide = batch.action == "hide"
    changed = 0
    now = utc_now()
    for entry in entries:
        comment = entry.comment
        if comment.status != ("hidden" if was_hide else "visible") or latest.get(comment.id) != entry.id:
            continue

        comment.status = "visible" if was_hide else "hidden"
        comment.removal_reason = None if was_hide else entry.previous_removal_reason
        comment.removal_detail = None if was_hide else entry.previous_removal_detail
        comment.modified_at = now
        _log(
            session,
            community,
            moderator,
            "restore_comment" if was_hide else "hide_comment",
            comment_id=comment.id,
            thread_id=comment.thread_id,
            target_community_user_id=comment.community_user_id,
            reason=None if was_hide else _log_reason(comment.removal_reason, comment.removal_detail),
            batch_id=batch.id,
        )
        changed += 1

    batch.undone_at = now
    batch.undone_by_community_user_id = moderator.id
    _log(session, community, moderator, "undo_batch", batch_id=batch.id)
    await session.commit()
    return changed, len(entries) - changed


#=============== Admin ===============


async def get_admin_overview(session: AsyncSession, *, community: Community) -> dict:
    staff = list(
        (
            await session.execute(
                select(CommunityUser)
                .where(CommunityUser.community_id == community.id, CommunityUser.last_staff_role.is_not(None))
                .order_by(CommunityUser.last_staff_role, CommunityUser.display_name)
            )
        )
        .scalars()
        .all()
    )

    since = utc_now() - timedelta(days=ACTIVITY_DAYS)
    activity = await session.execute(
        select(
            ModerationAction.moderator_community_user_id,
            ModerationAction.action,
            func.count(ModerationAction.id),
            func.max(ModerationAction.created_at),
        )
        .where(ModerationAction.community_id == community.id, ModerationAction.created_at >= since)
        .group_by(ModerationAction.moderator_community_user_id, ModerationAction.action)
    )
    counts: dict[UUID, dict[str, int]] = {}
    last_active: dict[UUID, datetime] = {}
    for moderator_id, action, count, latest in activity.all():
        counts.setdefault(moderator_id, {})[action] = count
        last_active[moderator_id] = max(latest, last_active.get(moderator_id, latest))

    suspended = set(
        (
            await session.execute(
                select(CommunityBan.community_user_id).where(
                    CommunityBan.community_id == community.id,
                    CommunityBan.community_user_id.in_([user.id for user in staff]),
                    *_active(utc_now()),
                )
            )
        )
        .scalars()
        .all()
    )

    origins = await session.execute(
        select(CommunityAllowedOrigin.origin)
        .where(CommunityAllowedOrigin.community_id == community.id)
        .order_by(CommunityAllowedOrigin.origin)
    )

    return {
        "activity_days": ACTIVITY_DAYS,
        "max_batch_size": community.max_batch_size,
        "max_daily_batch_changes": community.max_daily_batch_changes,
        "rules_url": community.rules_url,
        "klipy_app_key": community.klipy_app_key,
        "image_hosts": community.image_hosts or [],
        "origins": list(origins.scalars().all()),
        "staff": [
            {
                "user": user,
                "removed": counts.get(user.id, {}).get("hide_comment", 0),
                "restored": counts.get(user.id, {}).get("restore_comment", 0),
                "bans": counts.get(user.id, {}).get("ban_user", 0),
                "batches": sum(counts.get(user.id, {}).get(action, 0) for action in ("hide_batch", "restore_batch")),
                "last_active_at": last_active.get(user.id),
                "is_suspended": user.id in suspended,
            }
            for user in staff
        ],
    }


async def update_limits(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    max_batch_size: int,
    max_daily_batch_changes: int,
) -> None:
    before = f"{community.max_batch_size} at once, {community.max_daily_batch_changes} a day"
    after = f"{max_batch_size} at once, {max_daily_batch_changes} a day"
    if before == after:
        return

    community.max_batch_size = max_batch_size
    community.max_daily_batch_changes = max_daily_batch_changes
    _log(session, community, moderator, "update_limits", reason=f"{before} → {after}")
    await session.commit()


async def update_rules_url(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    rules_url: str | None,
) -> None:
    """Where the widget's Rules button links. Logged, like the other admin settings."""
    if rules_url == community.rules_url:
        return

    community.rules_url = rules_url
    _log(session, community, moderator, "update_rules", reason=rules_url or "cleared")
    await session.commit()


async def update_klipy_app_key(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    klipy_app_key: str | None,
) -> None:
    """GIFs in the comment box (app.core.gifs): on with a key, off without. Logged without the key itself."""
    before = community.klipy_app_key
    if klipy_app_key == before:
        return

    community.klipy_app_key = klipy_app_key
    change = "turned on" if before is None else "turned off" if klipy_app_key is None else "key changed"
    _log(session, community, moderator, "update_gifs", reason=change)
    await session.commit()


async def update_image_hosts(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    image_hosts: list[str],
) -> None:
    """Which hosts' images show in comment text. Logged as what was added and removed."""
    before = list(community.image_hosts or [])
    if image_hosts == before:
        return

    added = [host for host in image_hosts if host not in before]
    removed = [host for host in before if host not in image_hosts]
    community.image_hosts = image_hosts
    change = "; ".join(
        part
        for part in (
            f"added {', '.join(added)}" if added else "",
            f"removed {', '.join(removed)}" if removed else "",
        )
        if part
    ) or "reordered"
    _log(session, community, moderator, "update_image_hosts", reason=change)
    await session.commit()


#=============== Reports ===============


async def list_reported_comments(
    session: AsyncSession,
    *,
    community: Community,
    report_status: str,
    reason: str | None,
    sort: str,
    limit: int,
    offset: int,
):
    """The queue: comments with open reports, or with closed ones, which moderators have decided."""
    in_status = CommentReport.status.in_(["open"] if report_status == "open" else ["resolved", "dismissed"])
    latest = func.max(CommentReport.created_at)
    grouped = (
        select(CommentReport.comment_id)
        .join(Comment, Comment.id == CommentReport.comment_id)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Thread.community_id == community.id, in_status)
        .group_by(CommentReport.comment_id)
    )
    if reason:
        grouped = grouped.where(CommentReport.reason == reason)
    order = {
        "newest": (latest.desc(), CommentReport.comment_id.desc()),
        "oldest": (latest.asc(), CommentReport.comment_id.asc()),
        "most_reported": (func.count(CommentReport.id).desc(), latest.desc(), CommentReport.comment_id.desc()),
    }[sort]
    total = await session.scalar(select(func.count()).select_from(grouped.subquery()))
    rows = await session.execute(grouped.order_by(*order).limit(limit).offset(offset))
    comment_ids = [row.comment_id for row in rows]
    if not comment_ids:
        return [], int(total or 0)

    comments = await session.execute(
        select(Comment)
        .options(selectinload(Comment.community_user), selectinload(Comment.thread))
        .where(Comment.id.in_(comment_ids))
    )
    by_id = {comment.id: comment for comment in comments.scalars().all()}
    await _attach_context(session, list(by_id.values()))
    reports = await session.execute(
        select(CommentReport)
        .options(selectinload(CommentReport.reporter), selectinload(CommentReport.resolver))
        .where(CommentReport.comment_id.in_(comment_ids), in_status)
        .order_by(CommentReport.created_at.desc())
    )
    by_comment: dict[int, list[CommentReport]] = {}
    for report in reports.scalars().all():
        by_comment.setdefault(report.comment_id, []).append(report)

    return [(by_id[comment_id], by_comment.get(comment_id, [])) for comment_id in comment_ids], int(total or 0)


async def resolve_reports(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    comment_id: int,
    new_status: str,
) -> None:
    comment = await _comment_in_community(session, community, comment_id)
    if await _resolve_open_reports(session, moderator, [comment.id], new_status):
        _log(
            session,
            community,
            moderator,
            "dismiss_reports" if new_status == "dismissed" else "resolve_reports",
            comment_id=comment.id,
            thread_id=comment.thread_id,
            target_community_user_id=comment.community_user_id,
        )
    await session.commit()


async def reopen_reports(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    comment_id: int,
) -> None:
    """Puts a comment's closed reports back in the queue, for a decision that needs another look."""
    comment = await _comment_in_community(session, community, comment_id)
    if comment.status != "visible":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Restore the comment first")

    result = await session.execute(
        update(CommentReport)
        .where(CommentReport.comment_id == comment.id, CommentReport.status != "open")
        .values(status="open", resolved_at=None, resolved_by_community_user_id=None)
    )
    if result.rowcount:
        _log(
            session,
            community,
            moderator,
            "reopen_reports",
            comment_id=comment.id,
            thread_id=comment.thread_id,
            target_community_user_id=comment.community_user_id,
        )
    await session.commit()


#=============== Users ===============


async def _attach_user_counts(session: AsyncSession, community: Community, users: list[CommunityUser]) -> None:
    ids = [user.id for user in users]
    if not ids:
        return

    comments = await session.execute(
        select(Comment.community_user_id, Comment.status, func.count(Comment.id))
        .where(Comment.community_user_id.in_(ids))
        .group_by(Comment.community_user_id, Comment.status)
    )
    by_status: dict[tuple[UUID, str], int] = {(row[0], row[1]): row[2] for row in comments}

    reports = await session.execute(
        select(Comment.community_user_id, func.count(CommentReport.id))
        .join(CommentReport, CommentReport.comment_id == Comment.id)
        .where(Comment.community_user_id.in_(ids))
        .group_by(Comment.community_user_id)
    )
    report_counts: dict[UUID, int] = {row[0]: row[1] for row in reports}

    banned = await session.execute(
        select(CommunityBan.community_user_id).where(
            CommunityBan.community_id == community.id,
            CommunityBan.community_user_id.in_(ids),
            *_active(utc_now()),
        )
    )
    banned_ids = set(banned.scalars().all())

    for user in users:
        user.removed_count = by_status.get((user.id, "hidden"), 0)
        user.comment_count = sum(count for (owner, _), count in by_status.items() if owner == user.id)
        user.report_count = report_counts.get(user.id, 0)
        user.is_banned = user.id in banned_ids


async def search_users(
    session: AsyncSession,
    *,
    community: Community,
    search: str | None,
    only: str | None,
    sort: str,
    limit: int,
    offset: int,
):
    comment_count = (
        select(func.count(Comment.id)).where(Comment.community_user_id == CommunityUser.id).scalar_subquery()
    )
    removed_count = (
        select(func.count(Comment.id))
        .where(Comment.community_user_id == CommunityUser.id, Comment.status == "hidden")
        .scalar_subquery()
    )
    report_count = (
        select(func.count(CommentReport.id))
        .join(Comment, Comment.id == CommentReport.comment_id)
        .where(Comment.community_user_id == CommunityUser.id)
        .scalar_subquery()
    )

    query = select(CommunityUser).where(CommunityUser.community_id == community.id)
    if only == "banned":
        query = query.where(
            select(CommunityBan.id)
            .where(CommunityBan.community_user_id == CommunityUser.id, *_active(utc_now()))
            .exists()
        )
    elif only == "removed":
        query = query.where(removed_count > 0)
    elif only == "reported":
        query = query.where(report_count > 0)
    if search:
        pattern = "%" + _escape_like(search) + "%"
        query = query.where(
            or_(
                CommunityUser.display_name.ilike(pattern, escape="\\"),
                CommunityUser.external_user_id.ilike(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    by_name = (CommunityUser.display_name, CommunityUser.id)
    order = {
        "name": by_name,
        "newest": (CommunityUser.created_at.desc(), CommunityUser.id),
        "most_comments": (comment_count.desc(), *by_name),
        "most_removed": (removed_count.desc(), *by_name),
        "most_reported": (report_count.desc(), *by_name),
    }[sort]
    result = await session.execute(query.order_by(*order).limit(limit).offset(offset))
    users = list(result.scalars().all())
    await _attach_user_counts(session, community, users)
    return users, int(total or 0)


async def get_user(session: AsyncSession, *, community: Community, community_user_id: UUID) -> CommunityUser:
    """A user with everything moderators know about them here."""
    user = await _require_user(session, community, community_user_id)
    await _attach_user_counts(session, community, [user])

    bans = await session.execute(
        select(CommunityBan)
        .options(*BAN_DETAILS)
        .where(CommunityBan.community_id == community.id, CommunityBan.community_user_id == user.id)
        .order_by(CommunityBan.created_at.desc(), CommunityBan.id.desc())
    )
    notes = await session.execute(
        select(UserNote)
        .options(selectinload(UserNote.author))
        .where(UserNote.community_id == community.id, UserNote.community_user_id == user.id)
        .order_by(UserNote.created_at.desc(), UserNote.id.desc())
    )
    user.bans = list(bans.scalars().all())
    user.notes = list(notes.scalars().all())
    return user


async def add_note(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    community_user_id: UUID,
    body: str,
) -> UserNote:
    await _require_user(session, community, community_user_id)
    note = UserNote(
        community_id=community.id,
        community_user_id=community_user_id,
        author_community_user_id=moderator.id,
        body=body,
    )
    session.add(note)
    await session.commit()
    result = await session.execute(
        select(UserNote).options(selectinload(UserNote.author)).where(UserNote.id == note.id)
    )
    return result.scalars().one()


async def delete_note(session: AsyncSession, *, community: Community, note_id: int) -> None:
    note = await session.get(UserNote, note_id)
    if not note or note.community_id != community.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    await session.delete(note)
    await session.commit()


#=============== Threads and the log ===============


async def set_thread_locked(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    unique_id: str,
    locked: bool,
    reason: str | None,
) -> Thread:
    result = await session.execute(
        select(Thread).where(Thread.community_id == community.id, Thread.unique_id == unique_id)
    )
    thread = result.scalars().first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    thread.is_locked = locked
    _log(session, community, moderator, "lock_thread" if locked else "unlock_thread", thread_id=thread.id, reason=reason)
    await session.commit()
    await session.refresh(thread)
    return thread


async def list_actions(
    session: AsyncSession,
    *,
    community: Community,
    action: str | None,
    moderator: UUID | None,
    target: UUID | None,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
):
    conditions = [ModerationAction.community_id == community.id]
    if action:
        conditions.append(ModerationAction.action.in_(BATCH_SUMMARIES.get(action, [action])))
    # A batch reads as its one summary line, unless the log is about one user
    if not target:
        conditions.append(or_(ModerationAction.batch_id.is_(None), ModerationAction.comment_id.is_(None)))
    if moderator:
        conditions.append(ModerationAction.moderator_community_user_id == moderator)
    if target:
        conditions.append(ModerationAction.target_community_user_id == target)
    if since:
        conditions.append(ModerationAction.created_at >= since)
    if until:
        conditions.append(ModerationAction.created_at <= until)
    total = await session.scalar(select(func.count(ModerationAction.id)).where(*conditions))
    result = await session.execute(
        select(ModerationAction)
        .options(
            selectinload(ModerationAction.moderator),
            selectinload(ModerationAction.target),
            selectinload(ModerationAction.comment),
            selectinload(ModerationAction.thread),
            selectinload(ModerationAction.batch),
        )
        .where(*conditions)
        .order_by(ModerationAction.created_at.desc(), ModerationAction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)
