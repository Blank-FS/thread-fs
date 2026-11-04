# app/models/moderation.py

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.common import utc_now
from app.db.base import Base


class ModerationAction(Base):
    """The audit log: what a moderator did, to what, and why.

    Moderators are community users: staff come from the host site's token, not from ThreadFS accounts.
    """

    __tablename__ = "moderation_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )
    moderator_community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # hide_comment | restore_comment | ban_user | unban_user | lock_thread | unlock_thread
    action = Column(String(64), nullable=False)

    comment_id = Column(
        Integer,
        ForeignKey("comments.id", ondelete="SET NULL"),
        nullable=True,
    )
    thread_id = Column(
        Integer,
        ForeignKey("threads.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_moderation_actions_community_created_at", "community_id", "created_at"),
    )


class CommunityBan(Base):
    """A ban from posting and voting. No expiry means permanent; moderators can lift any ban."""

    __tablename__ = "community_bans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )
    community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    banned_by_community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reason = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    lifted_at = Column(DateTime(timezone=True), nullable=True)
    lifted_by_community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_community_bans_user", "community_id", "community_user_id"),
    )
