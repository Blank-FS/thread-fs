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


# Reasons that make sense anywhere. Anything specific to a community belongs in its own list.
DEFAULT_REASONS = [
    Reason("spam", "Spam"),
    Reason("harassment", "Harassment"),
    Reason("hate", "Hate speech"),
    Reason("sexual", "Sexual content"),
    Reason("other", "Something else"),
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
