# app/models/community_staff.py

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.core.common import utc_now


class CommunityStaff(Base):
    __tablename__ = "community_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    role = Column(
        String(32), nullable=False, default="moderator"
    )  # owner, admin, moderator

    __table_args__ = (
        UniqueConstraint("community_id", "user_id", name="uq_community_staff_user"),
        Index("ix_community_staff_user", "user_id"),
        Index("ix_community_staff_community", "community_id"),
    )
