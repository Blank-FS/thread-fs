# app/services/reason_service.py

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community_reason import CommunityReason


@dataclass(frozen=True)
class Reason:
    key: str
    label: str


# The reason itself says nothing, so a report with it has to say what's wrong, and a removal has to tell the author why
OTHER_REASON = "other"

# Reasons that make sense anywhere. Anything specific to a community belongs in its own list.
DEFAULT_REASONS = [
    Reason("spam", "Spam"),
    Reason("harassment", "Harassment or bullying"),
    Reason("hate", "Hate speech"),
    Reason("violence", "Threats or violence"),
    Reason("personal_info", "Personal information"),
    Reason("sexual", "Sexual content"),
    Reason("off_topic", "Off topic"),
    Reason(OTHER_REASON, "Other"),
]


async def list_reasons(session: AsyncSession, community_id: UUID) -> list[Reason]:
    result = await session.execute(
        select(CommunityReason)
        .where(CommunityReason.community_id == community_id)
        .order_by(CommunityReason.position, CommunityReason.id)
    )
    rows = result.scalars().all()
    return [Reason(row.key, row.label) for row in rows] or DEFAULT_REASONS


async def require_reason(session: AsyncSession, community_id: UUID, key: str) -> Reason:
    for reason in await list_reasons(session, community_id):
        if reason.key == key:
            return reason

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Unknown reason",
    )


async def replace_reasons(session: AsyncSession, community_id: UUID, reasons: list[Reason]) -> list[Reason]:
    """Reports and removals keep the label they were made with, so past ones survive any change here."""
    await session.execute(delete(CommunityReason).where(CommunityReason.community_id == community_id))
    session.add_all(
        CommunityReason(community_id=community_id, key=reason.key, label=reason.label, position=position)
        for position, reason in enumerate(reasons)
    )
    await session.commit()
    return await list_reasons(session, community_id)
