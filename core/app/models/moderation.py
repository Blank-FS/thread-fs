# from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, Integer
# from sqlalchemy.dialects.postgresql import UUID

# from app.db.base import Base
# from app.core.common import utc_now


# class ModerationAction(Base):
#     __tablename__ = "moderation_actions"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

#     community_id = Column(
#         UUID(as_uuid=True), ForeignKey("communities.id"), nullable=False
#     )
#     moderator_user_id = Column(
#         UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
#     )
#     comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)

#     action = Column(
#         String(64), nullable=False
#     )  # e.g. "remove_comment", "restore_comment", "lock_thread", "unlock_thread", "ban_user", "unban_user", "mark_spam", "mark_not_spam"
#     reason = Column(Text, nullable=True)


# class CommunityBan(Base):
#     __tablename__ = "community_bans"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

#     community_id = Column(
#         UUID(as_uuid=True), ForeignKey("communities.id"), nullable=False
#     )
#     community_user_id = Column(
#         UUID(as_uuid=True), ForeignKey("community_users.id"), nullable=True
#     )

#     reason = Column(Text, nullable=True)
#     expires_at = Column(DateTime(timezone=True), nullable=True)

#     __table_args__ = (
#         Index("ix_community_bans_user", "community_id", "community_user_id"),
#     )
