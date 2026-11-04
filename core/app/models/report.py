# app/models/report.py

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.common import utc_now
from app.db.base import Base


class CommentReport(Base):
    __tablename__ = "comment_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    comment_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
    )
    reporter_community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reason = Column(String(64), nullable=False)
    details = Column(Text, nullable=True)

    # open | resolved | dismissed
    status = Column(String(32), nullable=False, default="open")
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reporter = relationship("CommunityUser", foreign_keys=[reporter_community_user_id])

    __table_args__ = (
        # One report per person per comment
        UniqueConstraint(
            "comment_id",
            "reporter_community_user_id",
            name="uq_comment_reports_reporter",
        ),
        Index("ix_comment_reports_status_created_at", "status", "created_at"),
    )
