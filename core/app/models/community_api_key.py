# app/models/community_api_key.py

from sqlalchemy import Integer, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.core.common import utc_now


class CommunityApiKey(Base):
    __tablename__ = "community_api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Public key is safe to expose in the frontend embed.
    # Example: tfspub_demo_abc123
    public_key = Column(String(255), nullable=False, unique=True, index=True)

    # Secret hash is for server-side signing/verifying later.
    # Never expose this to frontend.
    secret_hash = Column(String(255), nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_community_api_keys_community_id", "community_id"),)
