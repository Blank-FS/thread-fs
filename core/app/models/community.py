# app/models/community.py

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.core.common import utc_now


class Community(Base):
    __tablename__ = "communities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    modified_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Owner ThreadFS dashboard user.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    thread_count = Column(Integer, nullable=False, default=0)

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    site_url = Column(String(2048), nullable=True)

    allow_anonymous_read = Column(Boolean, nullable=False, default=True)
    allow_anonymous_comment = Column(Boolean, nullable=False, default=False)

    # What a moderator can change in bulk, at once and in a day. Admins have no limit
    max_batch_size = Column(Integer, nullable=False, default=50, server_default="50")
    max_daily_batch_changes = Column(Integer, nullable=False, default=200, server_default="200")
    # The community's full comment rules, on its own site: the widget's Rules button links there. Set by admins.
    rules_url = Column(String(2048), nullable=True)
