# tests/integration/test_reply_preview.py

import pytest

from tests.factories import create_community_setup
from tests.integration.test_moderation import MOD, API, admin, headers, hide, mod, post_comment, user_id


async def top_level(client, setup, subject=None, **params):
    res = await client.get(
        f"{API}/comments",
        params={"thread_id": "anime:1", **params},
        headers=headers(setup, subject),
    )
    assert res.status_code == 200, res.text
    return {item["id"]: item for item in res.json()["items"]}


async def vote(client, setup, comment_id, subject, value=1):
    res = await client.post(
        f"{API}/comments/{comment_id}/votes",
        headers=headers(setup, subject),
        json={"value": value},
    )
    assert res.status_code == 200, res.text


@pytest.mark.anyio
async def test_no_preview_by_default(client, session):
    # A new community's setting is 0
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, content="Root")
    await post_comment(client, setup, subject="bob", content="Reply", parent_comment_id=int(root["id"]))

    items = await top_level(client, setup)

    assert items[root["id"]]["replies"] == []
    assert items[root["id"]]["replies_has_more"] is False


@pytest.mark.anyio
async def test_preview_brings_the_best_replies_and_says_how_many_more(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, content="Root")
    lonely = await post_comment(client, setup, content="No replies")
    parent = int(root["id"])
    first = await post_comment(client, setup, subject="bob", content="First", parent_comment_id=parent)
    second = await post_comment(client, setup, subject="carol", content="Second", parent_comment_id=parent)
    liked = await post_comment(client, setup, subject="dave", content="Liked", parent_comment_id=parent)
    # Below a reply: counted in the root's reply_count, but not one of its direct replies
    await post_comment(client, setup, subject="erin", content="Nested", parent_comment_id=int(first["id"]))
    await vote(client, setup, liked["id"], "alice")

    items = await top_level(client, setup, subject="alice", reply_preview=2)

    root_item = items[root["id"]]
    # The highest scored, then the first posted
    assert [reply["id"] for reply in root_item["replies"]] == [liked["id"], first["id"]]
    assert root_item["replies"][0]["viewer_vote"] == 1
    assert root_item["replies_total"] == 3
    assert root_item["replies_has_more"] is True
    assert root_item["replies_next_offset"] == 0
    assert second["id"] not in [reply["id"] for reply in root_item["replies"]]

    assert items[lonely["id"]]["replies"] == []


@pytest.mark.anyio
async def test_preview_of_every_reply_has_no_more(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, content="Root")
    await post_comment(client, setup, subject="bob", content="Only", parent_comment_id=int(root["id"]))

    item = (await top_level(client, setup, reply_preview=3))[root["id"]]

    assert len(item["replies"]) == 1
    assert item["replies_has_more"] is False
    assert item["replies_next_offset"] is None
    assert item["replies_total"] == 1


@pytest.mark.anyio
async def test_preview_skips_removed_replies_but_counts_them(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, content="Root")
    removed = await post_comment(client, setup, subject="spammer", content="Spam", parent_comment_id=int(root["id"]))
    kept = await post_comment(client, setup, subject="bob", content="Fine", parent_comment_id=int(root["id"]))
    await hide(client, setup, removed["id"])

    item = (await top_level(client, setup, reply_preview=2))[root["id"]]

    assert [reply["id"] for reply in item["replies"]] == [kept["id"]]
    # The removed one still holds its place in the full listing
    assert item["replies_total"] == 2
    assert item["replies_has_more"] is True


@pytest.mark.anyio
async def test_reply_listings_ignore_preview(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, content="Root")
    reply = await post_comment(client, setup, subject="bob", content="Reply", parent_comment_id=int(root["id"]))
    await post_comment(client, setup, subject="carol", content="Deeper", parent_comment_id=int(reply["id"]))

    items = await top_level(client, setup, parent_comment_id=int(root["id"]), reply_preview=2)

    assert items[reply["id"]]["replies"] == []


@pytest.mark.anyio
async def test_preview_is_capped(client, session):
    setup = await create_community_setup(session)

    res = await client.get(
        f"{API}/comments",
        params={"thread_id": "anime:1", "reply_preview": 6},
        headers=headers(setup),
    )

    assert res.status_code == 422


@pytest.mark.anyio
async def test_admins_set_the_community_preview_that_widgets_fall_back_to(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "boss", role="admin")
    await user_id(client, setup, "mod", role="moderator")
    root = await post_comment(client, setup, content="Root")
    parent = int(root["id"])
    for subject in ("bob", "carol", "dave"):
        await post_comment(client, setup, subject=subject, content="Reply", parent_comment_id=parent)
    url = f"{MOD}/admin/reply-preview"

    assert (await client.put(url, headers=mod(setup), json={"reply_preview": 2})).status_code == 403
    assert (await client.put(url, headers=admin(setup), json={"reply_preview": 6})).status_code == 422

    saved = await client.put(url, headers=admin(setup), json={"reply_preview": 2})
    assert saved.status_code == 200
    assert saved.json()["reply_preview"] == 2

    (entry,) = (await client.get(f"{MOD}/actions", headers=admin(setup))).json()["items"]
    assert entry["action"] == "update_reply_preview"
    assert entry["reason"] == "0 → 2"

    # Left out, the community's setting; asked for, the widget's own, 0 included
    assert len((await top_level(client, setup))[root["id"]]["replies"]) == 2
    assert len((await top_level(client, setup, reply_preview=1))[root["id"]]["replies"]) == 1
    assert (await top_level(client, setup, reply_preview=0))[root["id"]]["replies"] == []
