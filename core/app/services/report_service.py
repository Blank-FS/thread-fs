# app/services/report_service.py

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.models.community_user import CommunityUser
from app.models.report import CommentReport
from app.repositories import comment as comment_repo
from app.repositories import thread as thread_repo
from app.services import reason_service


async def report_comment(
    session: AsyncSession,
    *,
    community: Community,
    community_user: CommunityUser,
    comment_id: int,
    reason: str,
    details: str | None,
) -> None:
    """Reports a comment to the community's moderators. Reporting it again does nothing."""
    comment = await comment_repo.get_comment_by_id(session, comment_id)
    thread = await thread_repo.get_thread_by_id(session, comment.thread_id) if comment else None

    if not comment or comment.status != "visible" or not thread or thread.community_id != community.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    community_reason = await reason_service.require_reason(session, community.id, reason)

    existing = await session.execute(
        select(CommentReport.id).where(
            CommentReport.comment_id == comment_id,
            CommentReport.reporter_community_user_id == community_user.id,
        )
    )
    if existing.first():
        return

    session.add(
        CommentReport(
            comment_id=comment_id,
            reporter_community_user_id=community_user.id,
            reason=community_reason.key,
            reason_label=community_reason.label,
            details=details,
        )
    )
    await session.commit()
