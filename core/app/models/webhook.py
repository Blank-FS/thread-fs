# app/models/webhook.py

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.common import utc_now
from app.db.base import Base


class CommunityWebhook(Base):
    """An endpoint on the host site that receives the community's events (app.services.webhook_service)."""

    __tablename__ = "community_webhooks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    community_id = Column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
    )

    url = Column(String(2048), nullable=False)
    # Standard Webhooks format, "whsec_" + base64. Kept readable, since every delivery is signed with it; it's shown to
    # the community's owner once, when made (app.scripts.set_webhook).
    secret = Column(String(255), nullable=False)
    # Comma-separated event types, e.g. "comment.reply,comment.created"
    events = Column(String(512), nullable=False, default="comment.reply")
    is_enabled = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (Index("ix_community_webhooks_community_id", "community_id"),)

    def wants(self, event_type: str) -> bool:
        return self.is_enabled and event_type in {e.strip() for e in self.events.split(",")}


class WebhookDelivery(Base):
    """One event for one endpoint: the outbox. Written in the same transaction as what caused it, so it can't be lost,
    and sent by the delivery loop, which retries with backoff until it's delivered or gives up."""

    __tablename__ = "webhook_deliveries"

    # The webhook-id header ("msg_..."), the same on every retry so receivers can ignore repeats
    id = Column(String(64), primary_key=True)

    webhook_id = Column(
        Integer,
        ForeignKey("community_webhooks.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type = Column(String(64), nullable=False)
    # The exact body, so every retry sends (and signs) the same bytes
    payload = Column(Text, nullable=False)

    # pending, delivered or failed
    status = Column(String(16), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_error = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_webhook_deliveries_due", "status", "next_attempt_at"),
        Index("ix_webhook_deliveries_webhook_id", "webhook_id"),
    )
