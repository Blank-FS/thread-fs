# app/models/comment_vote.py

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.core.common import utc_now


class CommentVote(Base):
    __tablename__ = "comment_votes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    comment_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
    )

    community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 1 = upvote, -1 = downvote
    value = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    modified_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    __table_args__ = (
        UniqueConstraint(
            "comment_id",
            "community_user_id",
            name="uq_comment_votes_comment_user",
        ),
        Index("ix_comment_votes_comment_id", "comment_id"),
        Index("ix_comment_votes_community_user_id", "community_user_id"),
    )
