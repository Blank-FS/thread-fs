# app/models/moderation.py

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.common import utc_now
from app.db.base import Base


class ModerationBatch(Base):
    """One bulk action on comments: what the daily limit counts, and what an admin can undo in one step."""

    __tablename__ = "moderation_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

    # hide | restore
    action = Column(String(16), nullable=False)
    comment_count = Column(Integer, nullable=False)
    counts_toward_limit = Column(Boolean, nullable=False, default=True)

    undone_at = Column(DateTime(timezone=True), nullable=True)
    undone_by_community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_moderation_batches_moderator_created_at", "moderator_community_user_id", "created_at"),
    )


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
    # | dismiss_reports | resolve_reports | reopen_reports | hide_batch | restore_batch | undo_batch
    # | clear_avatar | clear_avatar_frame
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

    # A batch logs one summary entry, plus one entry per comment that the log only shows for a chosen user
    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("moderation_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # What a batch restore cleared from the comment, so undoing it can put that back
    previous_removal_reason = Column(String(128), nullable=True)
    previous_removal_detail = Column(String(200), nullable=True)

    batch = relationship("ModerationBatch", foreign_keys=[batch_id])
    moderator = relationship("CommunityUser", foreign_keys=[moderator_community_user_id])
    target = relationship("CommunityUser", foreign_keys=[target_community_user_id])
    comment = relationship("Comment", foreign_keys=[comment_id])
    thread = relationship("Thread", foreign_keys=[thread_id])

    __table_args__ = (
        Index("ix_moderation_actions_community_created_at", "community_id", "created_at"),
    )


class UserNote(Base):
    """A private note between moderators about a user. Never shown to the user."""

    __tablename__ = "community_user_notes"

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
    author_community_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("community_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    body = Column(Text, nullable=False)

    author = relationship("CommunityUser", foreign_keys=[author_community_user_id])

    __table_args__ = (
        Index("ix_community_user_notes_user", "community_id", "community_user_id"),
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

    community_user = relationship("CommunityUser", foreign_keys=[community_user_id])
    banned_by = relationship("CommunityUser", foreign_keys=[banned_by_community_user_id])
    lifted_by = relationship("CommunityUser", foreign_keys=[lifted_by_community_user_id])

    __table_args__ = (
        Index("ix_community_bans_user", "community_id", "community_user_id"),
    )
