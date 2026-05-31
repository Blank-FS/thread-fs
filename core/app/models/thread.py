# app/models/thread.py

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.core.common import utc_now


class Thread(Base):
    __tablename__ = "threads"

    # Basics
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    modified_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Associations
    community_id = Column(
        UUID(as_uuid=True), ForeignKey("communities.id"), nullable=False
    )
    unique_id = Column(String(512), nullable=False)

    # Stats
    upvote_count = Column(Integer, nullable=False, default=0)
    downvote_count = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)

    # Information
    title = Column(String(512), nullable=True)
    source_url = Column(String(2048), nullable=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("community_id", "unique_id"),
        Index("ix_threads_community_created", "community_id", "created_at"),
    )
