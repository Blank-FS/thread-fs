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
