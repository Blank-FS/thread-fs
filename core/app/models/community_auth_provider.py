# app/models/community_auth_provider.py

from sqlalchemy import (
    Integer,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.core.common import utc_now


class CommunityAuthProvider(Base):
    __tablename__ = "community_auth_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Example: "website123", "demo", "custom"
    issuer = Column(String(255), nullable=False)

    # Example: "HS256" for MVP, later "RS256"
    algorithm = Column(String(32), nullable=False, default="HS256")

    # For HS256 MVP, store a secret hash/encrypted secret in real production.
    # For local dev, plain secret is okay temporarily.
    secret = Column(Text, nullable=True)

    # For RS256 later.
    public_key_pem = Column(Text, nullable=True)

    audience = Column(String(255), nullable=False, default="threadfs")

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "community_id", "issuer", name="uq_community_auth_provider_issuer"
        ),
    )
