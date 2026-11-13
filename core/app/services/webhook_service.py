# app/services/webhook_service.py
"""Webhooks: tell a community's site when something happens, e.g. a reply to one of its users' comments, so the site
can notify them. Follows the Standard Webhooks spec (standardwebhooks.com): the webhook-id, webhook-timestamp and
webhook-signature headers, an HMAC-SHA256 signature over "<id>.<timestamp>.<body>", and "whsec_" secrets, so sites can
verify with any library for it.

Events are queued in webhook_deliveries in the same transaction as what caused them (an outbox), then sent by
run_delivery_loop, which retries with backoff for about a day. Several workers can run the loop: each claims rows with
SKIP LOCKED, so an event goes out once at a time.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.common import utc_now
from app.models.comment import Comment
from app.models.community_user import CommunityUser
from app.models.thread import Thread
from app.models.webhook import CommunityWebhook, WebhookDelivery

logger = logging.getLogger(__name__)

REPLY_EVENT = "comment.reply"
CREATED_EVENT = "comment.created"
# What a new endpoint receives unless told otherwise (app.scripts.set_webhook)
ALL_EVENTS = (REPLY_EVENT, CREATED_EVENT)

# For local development only: the demo community's webhook (DEMO_WEBHOOK_URL, app.db.init_db) and the dev listener
# (app.scripts.webhook_listener) share it, so nothing needs copying. Never used in production. Built from a readable
# phrase, so it's plainly not a real key (and secret scanners don't take it for one).
DEMO_SECRET = "whsec_" + base64.b64encode(b"threadfs-local-demo-webhook!").decode()

# How far a delivery's timestamp may be from now, for receivers (verify)
TIMESTAMP_TOLERANCE = timedelta(minutes=5)

# After each failed attempt, how long until the next: Standard Webhooks' schedule, about 27 hours in all
RETRY_DELAYS = [
    timedelta(seconds=5),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=5),
    timedelta(hours=10),
    timedelta(hours=10),
]

# How long a claimed delivery is left alone, so another worker doesn't send it while this one is
CLAIM_LEASE = timedelta(minutes=1)
REQUEST_TIMEOUT = 10.0
BATCH_SIZE = 20
EXCERPT_LENGTH = 140


# ── Secrets and signatures ─────────────────────────────────────────────────────


def generate_secret() -> str:
    return "whsec_" + base64.b64encode(secrets.token_bytes(24)).decode()


def sign(secret: str, msg_id: str, timestamp: int, body: str) -> str:
    """The webhook-signature header's value: "v1," and the base64 HMAC-SHA256 of "<id>.<timestamp>.<body>", keyed with
    the secret's decoded bytes."""
    key = base64.b64decode(secret.removeprefix("whsec_"))
    digest = hmac.new(key, f"{msg_id}.{timestamp}.{body}".encode(), hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def verify(secret: str, msg_id: str | None, timestamp: str | None, signatures: str | None, body: str, now: datetime | None = None) -> bool:
    """The receiving side, as a site would check a delivery: one of the space-separated "v1," signatures matches and the
    timestamp is recent. For the dev listener and tests; sites use their own language's Standard Webhooks library."""
    if not (msg_id and timestamp and signatures):
        return False
    try:
        sent = int(timestamp)
    except ValueError:
        return False
    if abs((now or utc_now()).timestamp() - sent) > TIMESTAMP_TOLERANCE.total_seconds():
        return False
    expected = sign(secret, msg_id, sent, body)
    return any(hmac.compare_digest(expected, signature) for signature in signatures.split(" "))


# ── Events ─────────────────────────────────────────────────────────────────────


def excerpt(markdown: str, length: int = EXCERPT_LENGTH) -> str:
    """A comment's start as plain text, for a notification: links keep their text, formatting and code fences go."""
    text = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`#>~|]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= length:
        return text
    cut = text[: length - 1]
    space = cut.rfind(" ")
    return (cut[:space] if space > length * 0.6 else cut).rstrip(" ,.;:") + "…"


def _user(user: CommunityUser) -> dict:
    return {
        "identity_provider": user.identity_provider,
        "external_user_id": user.external_user_id,
        "display_name": user.display_name,
    }


def _thread(thread: Thread) -> dict:
    return {"id": thread.unique_id, "title": thread.title, "url": thread.source_url}


def _comment(comment: Comment, author: CommunityUser, now: datetime) -> dict:
    return {
        "id": comment.id,
        # A comment that's only a GIF or an image says so, rather than nothing
        "excerpt": excerpt(comment.content) or ("[GIF]" if comment.gif else "[image]" if comment.image else ""),
        "created_at": comment.created_at.isoformat() if comment.created_at else now.isoformat(),
        "author": _user(author),
    }


async def _queue(session: AsyncSession, *, thread: Thread, event_type: str, data: dict) -> int:
    """Queues one event for each of the thread's community's endpoints that want it. Doesn't commit: it's part of the
    transaction that caused it. Returns how many were queued."""
    webhooks = (
        await session.execute(
            select(CommunityWebhook).where(CommunityWebhook.community_id == thread.community_id)
        )
    ).scalars().all()
    targets = [webhook for webhook in webhooks if webhook.wants(event_type)]
    if not targets:
        return 0

    now = utc_now()
    body = json.dumps(
        {"type": event_type, "timestamp": now.isoformat(), "data": data},
        separators=(",", ":"),
    )
    for webhook in targets:
        session.add(
            WebhookDelivery(
                id=f"msg_{secrets.token_hex(12)}",
                webhook_id=webhook.id,
                event_type=event_type,
                payload=body,
                status="pending",
                attempts=0,
                next_attempt_at=now,
            )
        )
    return len(targets)


async def enqueue_reply(
    session: AsyncSession,
    *,
    thread: Thread,
    reply: Comment,
    replier: CommunityUser,
    parent: Comment,
    parent_author: CommunityUser | None,
) -> int:
    """comment.reply: someone replied to a comment, so its author may want to know. Not for replying to yourself, nor to
    a comment that's deleted, removed or whose author is gone."""
    if (
        parent_author is None
        or parent.status != "visible"
        or parent.community_user_id == replier.id
    ):
        return 0
    return await _queue(
        session,
        thread=thread,
        event_type=REPLY_EVENT,
        data={
            "thread": _thread(thread),
            "comment": _comment(reply, replier, utc_now()),
            "parent_comment": {"id": parent.id, "author": _user(parent_author)},
        },
    )


async def enqueue_created(
    session: AsyncSession,
    *,
    thread: Thread,
    comment: Comment,
    author: CommunityUser,
) -> int:
    """comment.created: any new comment, top-level or a reply (parent_comment_id). For whatever the site makes of it,
    e.g. telling the owner of a thread (a profile, a post) about comments on it: ThreadFS has no notion of owners."""
    return await _queue(
        session,
        thread=thread,
        event_type=CREATED_EVENT,
        data={
            "thread": _thread(thread),
            "comment": _comment(comment, author, utc_now()),
            "parent_comment_id": comment.parent_comment_id,
        },
    )


# ── Delivery ───────────────────────────────────────────────────────────────────


async def _claim_due(session_maker: async_sessionmaker, now: datetime) -> list[tuple[WebhookDelivery, CommunityWebhook]]:
    """Takes up to BATCH_SIZE due deliveries for this worker: leases them (pushes next_attempt_at on) and commits, so the
    sending happens outside any transaction and no other worker picks them up meanwhile."""
    async with session_maker() as session:
        rows = (
            await session.execute(
                select(WebhookDelivery, CommunityWebhook)
                .join(CommunityWebhook, CommunityWebhook.id == WebhookDelivery.webhook_id)
                .where(
                    WebhookDelivery.status == "pending",
                    WebhookDelivery.next_attempt_at <= now,
                    # A disabled endpoint's events wait until it's enabled again
                    CommunityWebhook.is_enabled.is_(True),
                )
                .order_by(WebhookDelivery.next_attempt_at)
                .limit(BATCH_SIZE)
                .with_for_update(of=WebhookDelivery, skip_locked=True)
            )
        ).all()
        for delivery, _ in rows:
            delivery.next_attempt_at = now + CLAIM_LEASE
        await session.commit()
        return [(delivery, webhook) for delivery, webhook in rows]


async def _send(client: httpx.AsyncClient, delivery: WebhookDelivery, webhook: CommunityWebhook) -> str | None:
    """Sends one delivery. None on a 2xx, else why it failed."""
    timestamp = int(utc_now().timestamp())
    try:
        response = await client.post(
            webhook.url,
            content=delivery.payload.encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ThreadFS-Webhooks/1.0",
                "webhook-id": delivery.id,
                "webhook-timestamp": str(timestamp),
                "webhook-signature": sign(webhook.secret, delivery.id, timestamp, delivery.payload),
            },
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as err:
        return f"{type(err).__name__}: {err}"[:512]
    if 200 <= response.status_code < 300:
        return None
    return f"HTTP {response.status_code}"


async def deliver_due(
    session_maker: async_sessionmaker,
    client: httpx.AsyncClient,
    *,
    now: datetime | None = None,
) -> int:
    """Sends what's due and records each outcome. Returns how many were attempted."""
    now = now or utc_now()
    claimed = await _claim_due(session_maker, now)
    if not claimed:
        return 0

    outcomes = [(delivery.id, await _send(client, delivery, webhook)) for delivery, webhook in claimed]

    async with session_maker() as session:
        for delivery_id, error in outcomes:
            delivery = await session.get(WebhookDelivery, delivery_id)
            if delivery is None:
                continue
            delivery.attempts += 1
            if error is None:
                delivery.status = "delivered"
                delivery.delivered_at = utc_now()
                delivery.last_error = None
            elif delivery.attempts > len(RETRY_DELAYS):
                delivery.status = "failed"
                delivery.last_error = error
                logger.warning("Webhook %s gave up after %s attempts: %s", delivery_id, delivery.attempts, error)
            else:
                delivery.next_attempt_at = utc_now() + RETRY_DELAYS[delivery.attempts - 1]
                delivery.last_error = error
        await session.commit()

    return len(claimed)


async def run_delivery_loop(session_maker: async_sessionmaker, poll_seconds: float) -> None:
    """Sends queued events until cancelled (started in app.main's lifespan)."""
    async with httpx.AsyncClient(follow_redirects=False) as client:
        while True:
            try:
                # A full batch suggests more are waiting, so go again straight away
                while await deliver_due(session_maker, client) >= BATCH_SIZE:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Webhook delivery loop failed; trying again shortly")
            await asyncio.sleep(poll_seconds)
