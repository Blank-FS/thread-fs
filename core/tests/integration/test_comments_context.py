# tests/integration/test_comments_context.py

import itertools

import pytest

from tests.factories import create_community_setup
from tests.helpers import create_test_token, embed_headers


# Each comment by a different user, so a test doesn't hit the per-user posting limit
_users = itertools.count()


async def _post(client, setup, *, thread_id="anime:1", content="hi", parent=None):
    token = create_test_token(secret=setup["secret"], issuer=setup["issuer"], subject=f"user-{next(_users)}")
    res = await client.post(
        "/api/v1/embed/comments",
        headers=embed_headers(public_key=setup["public_key"], origin=setup["origin"], token=token),
        json={
            "thread_id": thread_id,
            "title": "Anime 1",
            "source_url": "https://example.com/anime/1",
            "content": content,
            "parent_comment_id": parent,
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


async def _context(client, setup, comment_id, *, thread_id="anime:1", **params):
    return await client.get(
        f"/api/v1/embed/comments/{comment_id}/context",
        params={"thread_id": thread_id, **params},
        headers=embed_headers(public_key=setup["public_key"], origin=setup["origin"]),
    )


@pytest.mark.anyio
async def test_context_is_the_chain_down_to_the_comment(client, session):
    setup = await create_community_setup(session)

    root = await _post(client, setup, content="root")
    await _post(client, setup, content="another top-level comment")
    child = await _post(client, setup, content="child", parent=root)
    await _post(client, setup, content="child's sibling", parent=root)
    target = await _post(client, setup, content="target", parent=child)
    reply = await _post(client, setup, content="reply to target", parent=target)

    res = await _context(client, setup, target)

    assert res.status_code == 200
    body = res.json()
    assert body["focused_comment_id"] == target

    # Only the chain: no other top-level comment, no sibling
    assert body["root"]["id"] == root
    assert [c["id"] for c in body["root"]["replies"]] == [child]
    # The sibling isn't included, but the top-level comment says there's more, from the start of its replies
    assert body["root"]["replies_has_more"] is True
    assert body["root"]["replies_next_offset"] == 0
    assert body["root"]["replies_total"] == 2
    level2 = body["root"]["replies"][0]
    assert [c["id"] for c in level2["replies"]] == [target]
    assert level2["replies_has_more"] is False
    assert level2["replies_next_offset"] is None

    # The comment itself comes with its replies
    focused = level2["replies"][0]
    assert focused["content"] == "target"
    assert [c["id"] for c in focused["replies"]] == [reply]
    assert focused["replies_has_more"] is False
    assert focused["replies_next_offset"] is None


@pytest.mark.anyio
async def test_context_pages_the_comments_replies(client, session):
    setup = await create_community_setup(session)

    target = await _post(client, setup, content="target")
    first = await _post(client, setup, content="first", parent=target)
    await _post(client, setup, content="second", parent=target)

    res = await _context(client, setup, target, limit=1)

    assert res.status_code == 200
    root = res.json()["root"]
    assert root["id"] == target
    assert [c["id"] for c in root["replies"]] == [first]
    assert root["replies_has_more"] is True
    assert root["replies_next_offset"] == 1
    assert root["replies_total"] == 2


@pytest.mark.anyio
async def test_context_of_a_comment_in_another_thread_is_not_found(client, session):
    setup = await create_community_setup(session)

    elsewhere = await _post(client, setup, thread_id="anime:2")
    await _post(client, setup, thread_id="anime:1")

    assert (await _context(client, setup, elsewhere, thread_id="anime:1")).status_code == 404
    assert (await _context(client, setup, 999999, thread_id="anime:1")).status_code == 404
    assert (await _context(client, setup, elsewhere, thread_id="missing")).status_code == 404
