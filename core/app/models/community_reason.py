# app/models/community_reason.py

from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class CommunityReason(Base):
    """A community's own list of why a comment breaks its rules, used both for reporting and for removing comments.

    A community with no rows uses the defaults in app.services.reason_service.
    """

    __tablename__ = "community_reasons"

    id = Column(Integer, primary_key=True, autoincrement=True)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )

    key = Column(String(64), nullable=False)
    label = Column(String(128), nullable=False)
    position = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("community_id", "key", name="uq_community_reasons_key"),
    )
