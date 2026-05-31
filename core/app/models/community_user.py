# app/models/community_user.py

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.core.common import utc_now


class CommunityUser(Base):
    __tablename__ = "community_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )

    identity_provider = Column(String(32), nullable=False, default="external")
    external_user_id = Column(String(255), nullable=False)

    threadfs_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(2048), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    modified_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
