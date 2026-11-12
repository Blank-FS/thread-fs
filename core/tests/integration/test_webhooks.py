# tests/integration/test_webhooks.py

import base64
import hashlib
import hmac
import itertools
import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.common import utc_now
from app.models.webhook import CommunityWebhook, WebhookDelivery
from app.services import webhook_service
from tests.conftest import TestSessionLocal
from tests.factories import create_community_setup
from tests.helpers import create_test_token, embed_headers

_users = itertools.count()


async def _post(client, setup, *, subject=None, parent=None, content="hi"):
    token = create_test_token(
        secret=setup["secret"],
        issuer=setup["issuer"],
        subject=subject or f"user-{next(_users)}",
        username=subject or "Someone",
    )
    res = await client.post(
        "/api/v1/embed/comments",
        headers=embed_headers(public_key=setup["public_key"], origin=setup["origin"], token=token),
        json={
            "thread_id": "anime:1",
            "title": "Anime 1",
            "source_url": "https://example.com/anime/1",
            "content": content,
            "parent_comment_id": parent,
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


async def _add_webhook(session, setup, **fields) -> CommunityWebhook:
    webhook = CommunityWebhook(
        community_id=setup["community"].id,
        url="https://site.example/hooks/threadfs",
        secret=webhook_service.generate_secret(),
        events=fields.pop("events", "comment.reply"),
        is_enabled=fields.pop("is_enabled", True),
    )
    session.add(webhook)
    await session.commit()
    return webhook


async def _deliveries():
    async with TestSessionLocal() as session:
        return (await session.execute(select(WebhookDelivery))).scalars().all()


@pytest.mark.anyio
async def test_a_reply_queues_an_event_for_the_parents_author(client, session):
    setup = await create_community_setup(session)
    await _add_webhook(session, setup)

    parent = await _post(client, setup, subject="mira", content="The ending was great")
    reply = await _post(client, setup, subject="sora", parent=parent, content="**Agreed**, see [this](https://x.example)")

    [delivery] = await _deliveries()
    assert delivery.status == "pending" and delivery.event_type == "comment.reply"
    assert delivery.id.startswith("msg_")

    body = json.loads(delivery.payload)
    assert body["type"] == "comment.reply"
    data = body["data"]
    assert data["thread"]["id"] == "anime:1"
    assert data["comment"]["id"] == reply
    assert data["comment"]["excerpt"] == "Agreed, see this"
    assert data["comment"]["author"]["external_user_id"] == "sora"
    assert data["parent_comment"]["id"] == parent
    assert data["parent_comment"]["author"]["external_user_id"] == "mira"


@pytest.mark.anyio
async def test_no_event_for_top_level_comments_self_replies_or_without_a_webhook(client, session):
    setup = await create_community_setup(session)

    # No webhook yet
    parent = await _post(client, setup, subject="mira")
    await _post(client, setup, subject="sora", parent=parent)
    assert await _deliveries() == []

    await _add_webhook(session, setup)
    # A top-level comment, and a reply to your own comment
    own = await _post(client, setup, subject="kai")
    await _post(client, setup, subject="kai", parent=own)
    assert await _deliveries() == []


@pytest.mark.anyio
async def test_a_disabled_webhook_or_one_without_the_event_gets_nothing(client, session):
    setup = await create_community_setup(session)
    await _add_webhook(session, setup, is_enabled=False)
    await _add_webhook(session, setup, events="comment.edited")

    parent = await _post(client, setup, subject="mira")
    await _post(client, setup, subject="sora", parent=parent)
    assert await _deliveries() == []


@pytest.mark.anyio
async def test_delivery_is_signed_as_standard_webhooks_describes(client, session):
    setup = await create_community_setup(session)
    webhook = await _add_webhook(session, setup)
    parent = await _post(client, setup, subject="mira")
    await _post(client, setup, subject="sora", parent=parent)

    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await webhook_service.deliver_due(TestSessionLocal, http) == 1

    [request] = received
    body = request.content.decode()
    msg_id, timestamp = request.headers["webhook-id"], request.headers["webhook-timestamp"]
    # Worked out here from the spec, not with webhook_service.sign
    key = base64.b64decode(webhook.secret.removeprefix("whsec_"))
    expected = base64.b64encode(hmac.new(key, f"{msg_id}.{timestamp}.{body}".encode(), hashlib.sha256).digest()).decode()
    assert request.headers["webhook-signature"] == f"v1,{expected}"
    assert str(request.url) == webhook.url

    [delivery] = await _deliveries()
    assert delivery.status == "delivered" and delivery.attempts == 1 and delivery.delivered_at is not None
    assert delivery.id == msg_id and delivery.payload == body


@pytest.mark.anyio
async def test_a_failed_delivery_is_retried_later_then_given_up(client, session):
    setup = await create_community_setup(session)
    await _add_webhook(session, setup)
    parent = await _post(client, setup, subject="mira")
    await _post(client, setup, subject="sora", parent=parent)

    failing = httpx.MockTransport(lambda request: httpx.Response(500))
    async with httpx.AsyncClient(transport=failing) as http:
        before = utc_now()
        assert await webhook_service.deliver_due(TestSessionLocal, http) == 1
        [delivery] = await _deliveries()
        assert delivery.status == "pending" and delivery.attempts == 1
        assert delivery.last_error == "HTTP 500"
        assert delivery.next_attempt_at >= before + timedelta(seconds=4)

        # Not due yet, so nothing is sent
        assert await webhook_service.deliver_due(TestSessionLocal, http) == 0

        # On its last attempt, a failure gives up
        async with TestSessionLocal() as s:
            row = await s.get(WebhookDelivery, delivery.id)
            row.attempts = len(webhook_service.RETRY_DELAYS)
            row.next_attempt_at = utc_now()
            await s.commit()
        assert await webhook_service.deliver_due(TestSessionLocal, http) == 1
        [delivery] = await _deliveries()
        assert delivery.status == "failed"


@pytest.mark.anyio
async def test_events_for_a_webhook_disabled_later_wait(client, session):
    setup = await create_community_setup(session)
    webhook = await _add_webhook(session, setup)
    parent = await _post(client, setup, subject="mira")
    await _post(client, setup, subject="sora", parent=parent)

    async with TestSessionLocal() as s:
        (await s.get(CommunityWebhook, webhook.id)).is_enabled = False
        await s.commit()

    sent = httpx.MockTransport(lambda request: httpx.Response(200))
    async with httpx.AsyncClient(transport=sent) as http:
        assert await webhook_service.deliver_due(TestSessionLocal, http) == 0
    [delivery] = await _deliveries()
    assert delivery.status == "pending"


def test_excerpt_is_plain_text_cut_at_a_word():
    assert webhook_service.excerpt("Look:\n\n```\ncode()\n```\n\n> quoted _text_") == "Look: quoted text"
    long = "word " * 60
    cut = webhook_service.excerpt(long)
    assert len(cut) <= webhook_service.EXCERPT_LENGTH and cut.endswith("word…")


def test_verify_accepts_what_sign_makes_and_nothing_else():
    secret, body = webhook_service.DEMO_SECRET, '{"type":"comment.reply"}'
    now = utc_now()
    ts = int(now.timestamp())
    good = webhook_service.sign(secret, "msg_1", ts, body)

    assert webhook_service.verify(secret, "msg_1", str(ts), good, body, now)
    # One good signature among several, as while a secret is rotated
    assert webhook_service.verify(secret, "msg_1", str(ts), f"v1,bm9wZQ== {good}", body, now)
    assert not webhook_service.verify(secret, "msg_1", str(ts), good, body + " ", now)
    assert not webhook_service.verify(secret, "msg_2", str(ts), good, body, now)
    assert not webhook_service.verify(secret, "msg_1", str(ts), good, body, now + timedelta(minutes=6))
    assert not webhook_service.verify(secret, None, str(ts), good, body, now)


@pytest.mark.anyio
async def test_every_new_comment_queues_comment_created(client, session):
    setup = await create_community_setup(session)
    await _add_webhook(session, setup, events="comment.created")

    top = await _post(client, setup, subject="mira", content="On your **wall**")
    reply = await _post(client, setup, subject="mira", parent=top, content="And a follow-up")

    events = sorted((json.loads(d.payload) for d in await _deliveries()), key=lambda e: e["data"]["comment"]["id"])
    assert [e["type"] for e in events] == ["comment.created", "comment.created"]
    assert events[0]["data"]["comment"]["id"] == top
    assert events[0]["data"]["parent_comment_id"] is None
    assert events[0]["data"]["comment"]["excerpt"] == "On your wall"
    assert events[0]["data"]["comment"]["author"]["external_user_id"] == "mira"
    assert events[0]["data"]["thread"]["id"] == "anime:1"
    # A reply (even to your own comment) is reported too, with its parent
    assert events[1]["data"]["comment"]["id"] == reply
    assert events[1]["data"]["parent_comment_id"] == top


@pytest.mark.anyio
async def test_an_endpoint_with_both_events_gets_both_for_a_reply(client, session):
    setup = await create_community_setup(session)
    await _add_webhook(session, setup, events="comment.reply,comment.created")

    parent = await _post(client, setup, subject="mira")
    await _post(client, setup, subject="sora", parent=parent)

    assert sorted(d.event_type for d in await _deliveries()) == ["comment.created", "comment.created", "comment.reply"]
