# from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, Integer
# from sqlalchemy.dialects.postgresql import UUID

# from app.db.base import Base
# from app.core.common import utc_now


# class CommentReport(Base):
#     __tablename__ = "comment_reports"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

#     comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False)
#     reporter_community_user_id = Column(
#         UUID(as_uuid=True), ForeignKey("community_users.id"), nullable=True
#     )

#     reason = Column(String(64), nullable=False)
#     details = Column(Text, nullable=True)
#     status = Column(String(32), nullable=False, default="open")

#     __table_args__ = (
#         Index("ix_comment_reports_comment", "comment_id"),
#         Index("ix_comment_reports_status", "status"),
#     )
