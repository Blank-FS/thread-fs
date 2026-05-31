# app/models/community_allowed_origin.py

from sqlalchemy import (
    Integer,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.core.common import utc_now


class CommunityAllowedOrigin(Base):
    __tablename__ = "community_allowed_origins"

    id = Column(Integer, primary_key=True, autoincrement=True)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )

    origin = Column(String(255), nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "community_id",
            "origin",
            name="uq_community_allowed_origins_community_origin",
        ),
        Index("ix_community_allowed_origins_community_id", "community_id"),
    )
