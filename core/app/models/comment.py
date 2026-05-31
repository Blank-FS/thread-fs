# app/models/comment.py

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.core.common import utc_now


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    modified_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    thread_id = Column(
        Integer,
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
    )

    parent_comment_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
    )

    community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="CASCADE"),
        nullable=False,
    )

    deleted_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    community_user = relationship(
        "CommunityUser",
        foreign_keys=[community_user_id],
    )

    deleted_by_user = relationship(
        "CommunityUser",
        foreign_keys=[deleted_by_user_id],
    )

    upvote_count = Column(Integer, nullable=False, default=0)
    downvote_count = Column(Integer, nullable=False, default=0)
    reply_count = Column(Integer, nullable=False, default=0)

    content = Column(Text, nullable=False)

    # visible | deleted | hidden
    status = Column(String(32), nullable=False, default="visible")

    ip_hash = Column(String(128), nullable=True)
    user_agent = Column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_comments_thread_created_at", "thread_id", "created_at"),
        Index("ix_comments_parent_created_at", "parent_comment_id", "created_at"),
        Index(
            "ix_comments_community_user_created_at",
            "community_user_id",
            "created_at",
        ),
    )
