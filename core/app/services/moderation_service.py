# app/services/moderation_service.py

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.common import utc_now
from app.models.comment import Comment
from app.models.community import Community
from app.models.community_user import CommunityUser
from app.models.moderation import CommunityBan, ModerationAction
from app.models.report import CommentReport
from app.models.thread import Thread
from app.schemas.moderation import CommentFilters


#=============== Bans ===============


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
    target = await session.get(CommunityUser, community_user_id)
    if not target or target.community_id != community.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if expires_at is not None and expires_at <= utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A ban must expire in the future")

    if await get_active_ban(session, community_id=community.id, community_user_id=community_user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already banned")

    ban = CommunityBan(
        community_id=community.id,
        community_user_id=community_user_id,
        banned_by_community_user_id=moderator.id,
        reason=reason,
        expires_at=expires_at,
    )
    session.add(ban)
    _log(session, community, moderator, "ban_user", target_community_user_id=community_user_id, reason=reason)
    await session.commit()
    return await _load_ban(session, ban.id)


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

    ban.lifted_at = utc_now()
    ban.lifted_by_community_user_id = moderator.id
    _log(session, community, moderator, "unban_user", target_community_user_id=ban.community_user_id, reason=reason)
    await session.commit()
    return await _load_ban(session, ban_id)


async def _load_ban(session: AsyncSession, ban_id: int) -> CommunityBan:
    result = await session.execute(
        select(CommunityBan)
        .options(selectinload(CommunityBan.community_user))
        .where(CommunityBan.id == ban_id)
        .execution_options(populate_existing=True)
    )
    return result.scalars().one()


async def list_bans(session: AsyncSession, *, community: Community, active_only: bool, limit: int, offset: int):
    conditions = [CommunityBan.community_id == community.id]
    if active_only:
        conditions.extend(_active(utc_now()))
    total = await session.scalar(select(func.count(CommunityBan.id)).where(*conditions))
    result = await session.execute(
        select(CommunityBan)
        .options(selectinload(CommunityBan.community_user))
        .where(*conditions)
        .order_by(CommunityBan.created_at.desc(), CommunityBan.id.desc())
        .limit(limit)
        .offset(offset)
    )
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
    if filters.since:
        query = query.where(Comment.created_at >= filters.since)
    if filters.until:
        query = query.where(Comment.created_at <= filters.until)
    if search:
        pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(Comment.content.ilike(pattern, escape="\\"))
    return query


async def search_comments(
    session: AsyncSession,
    *,
    community: Community,
    filters: CommentFilters,
    status_filter: str | None,
    search: str | None,
    limit: int,
    offset: int,
):
    query = _comments_query(community, filters, status_filter=status_filter, search=search)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(
        query.options(selectinload(Comment.community_user), selectinload(Comment.thread))
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)


async def _load_comment(session: AsyncSession, comment_id: int) -> Comment:
    result = await session.execute(
        select(Comment)
        .options(selectinload(Comment.community_user), selectinload(Comment.thread))
        .where(Comment.id == comment_id)
        .execution_options(populate_existing=True)
    )
    return result.scalars().one()


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


async def _resolve_open_reports(session: AsyncSession, moderator: CommunityUser, comment_ids: list[int], new_status: str):
    await session.execute(
        update(CommentReport)
        .where(CommentReport.comment_id.in_(comment_ids), CommentReport.status == "open")
        .values(status=new_status, resolved_at=utc_now(), resolved_by_community_user_id=moderator.id)
    )


async def hide_comment(
    session: AsyncSession,
    *,
    community: Community,
    moderator: CommunityUser,
    comment_id: int,
    reason: str | None,
) -> Comment:
    comment = await _comment_in_community(session, community, comment_id)
    if comment.status != "visible":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Comment isn't visible")

    comment.status = "hidden"
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
    reason: str | None,
    dry_run: bool,
) -> tuple[int, int]:
    """Hides or restores everything matching the filters: the cleanup for a site or user gone wrong. Every comment gets
    its own log entry, so a batch can be reviewed, and the same filters with "restore" undo it."""
    from_status, to_status = ("visible", "hidden") if action == "hide" else ("hidden", "visible")
    result = await session.execute(_comments_query(community, filters, status_filter=from_status, search=None))
    comments = list(result.scalars().all())
    if dry_run or not comments:
        return len(comments), 0

    now = utc_now()
    for comment in comments:
        comment.status = to_status
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
        )
    if action == "hide":
        await _resolve_open_reports(session, moderator, [comment.id for comment in comments], "resolved")
    await session.commit()
    return len(comments), len(comments)


#=============== Reports ===============


async def list_reported_comments(session: AsyncSession, *, community: Community, limit: int, offset: int):
    """The queue: comments with open reports, most recently reported first."""
    grouped = (
        select(CommentReport.comment_id, func.max(CommentReport.created_at).label("latest"))
        .join(Comment, Comment.id == CommentReport.comment_id)
        .join(Thread, Thread.id == Comment.thread_id)
        .where(Thread.community_id == community.id, CommentReport.status == "open")
        .group_by(CommentReport.comment_id)
    )
    total = await session.scalar(select(func.count()).select_from(grouped.subquery()))
    rows = await session.execute(grouped.order_by(func.max(CommentReport.created_at).desc()).limit(limit).offset(offset))
    comment_ids = [row.comment_id for row in rows]
    if not comment_ids:
        return [], int(total or 0)

    comments = await session.execute(
        select(Comment)
        .options(selectinload(Comment.community_user), selectinload(Comment.thread))
        .where(Comment.id.in_(comment_ids))
    )
    by_id = {comment.id: comment for comment in comments.scalars().all()}
    reports = await session.execute(
        select(CommentReport)
        .options(selectinload(CommentReport.reporter))
        .where(CommentReport.comment_id.in_(comment_ids), CommentReport.status == "open")
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
    await _resolve_open_reports(session, moderator, [comment.id], new_status)
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


async def list_actions(session: AsyncSession, *, community: Community, limit: int, offset: int):
    conditions = [ModerationAction.community_id == community.id]
    total = await session.scalar(select(func.count(ModerationAction.id)).where(*conditions))
    result = await session.execute(
        select(ModerationAction)
        .options(selectinload(ModerationAction.moderator), selectinload(ModerationAction.target))
        .where(*conditions)
        .order_by(ModerationAction.created_at.desc(), ModerationAction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)
