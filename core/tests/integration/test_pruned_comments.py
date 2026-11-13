# tests/integration/test_pruned_comments.py

import pytest

from tests.factories import create_community_setup
from tests.integration.test_moderation import (
    MOD,
    API,
    admin,
    headers,
    hide,
    mod,
    post_comment,
    thread_items,
    user_id,
)


async def delete(client, setup, comment, subject):
    res = await client.delete(f"{API}/comments/{comment['id']}", headers=headers(setup, subject))
    assert res.status_code == 200, res.text
    return res.json()


async def replies(client, setup, parent, subject=None):
    res = await client.get(
        f"{API}/comments",
        params={"thread_id": "anime:1", "parent_comment_id": int(parent["id"])},
        headers=headers(setup, subject),
    )
    assert res.status_code == 200, res.text
    return res.json()


async def comment_count(client, setup, thread="anime:1"):
    res = await client.post(f"{API}/threads/resolve", headers=headers(setup), json={"thread_id": thread})
    assert res.status_code == 200, res.text
    return res.json()["thread"]["comment_count"]


def by_id(items):
    return {item["id"]: item for item in items}


@pytest.mark.anyio
async def test_a_deleted_comment_with_nothing_below_leaves_the_thread(client, session):
    setup = await create_community_setup(session)
    gone = await post_comment(client, setup, subject="alice", content="Bye")
    kept = await post_comment(client, setup, subject="bob", content="Staying")
    assert await comment_count(client, setup) == 2

    await delete(client, setup, gone, "alice")

    for viewer in (None, "alice", "bob"):
        assert [item["id"] for item in await thread_items(client, setup, viewer)] == [kept["id"]]
    assert await comment_count(client, setup) == 1


@pytest.mark.anyio
async def test_a_deleted_comment_keeps_its_place_while_a_reply_shows(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, subject="alice", content="Root")
    middle = await post_comment(client, setup, subject="bob", content="Middle", parent_comment_id=int(root["id"]))
    leaf = await post_comment(client, setup, subject="carol", content="Leaf", parent_comment_id=int(middle["id"]))

    await delete(client, setup, root, "alice")
    await delete(client, setup, middle, "bob")

    # The leaf still shows, so both above it keep their place, empty
    (item,) = await thread_items(client, setup)
    assert item["id"] == root["id"]
    assert item["status"] == "deleted"
    assert item["reply_count"] == 1
    (reply,) = (await replies(client, setup, root))["items"]
    assert reply["id"] == middle["id"]
    assert reply["reply_count"] == 1
    assert await comment_count(client, setup) == 1

    # Once the last visible comment goes, the whole chain does
    await delete(client, setup, leaf, "carol")
    assert await thread_items(client, setup) == []
    assert await comment_count(client, setup) == 0


@pytest.mark.anyio
async def test_a_removed_comment_with_nothing_below_shows_only_to_its_author(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, subject="alice", content="Root")
    removed = await post_comment(client, setup, subject="spammer", content="Spam", parent_comment_id=int(root["id"]))
    kept = await post_comment(client, setup, subject="bob", content="Fine", parent_comment_id=int(root["id"]))

    await hide(client, setup, removed["id"])

    assert [item["id"] for item in (await replies(client, setup, root, "bob"))["items"]] == [kept["id"]]
    assert (await replies(client, setup, root, "bob"))["total"] == 1
    own = by_id((await replies(client, setup, root, "spammer"))["items"])
    assert own[removed["id"]]["status"] == "hidden"
    assert own[removed["id"]]["content"] == "Spam"
    assert (await thread_items(client, setup, "bob"))[0]["reply_count"] == 1
    assert await comment_count(client, setup) == 2

    # And to others again once restored
    restored = await client.post(f"{MOD}/comments/{removed['id']}/restore", headers=mod(setup), json={})
    assert restored.status_code == 200, restored.text
    assert len((await replies(client, setup, root, "bob"))["items"]) == 2
    assert (await thread_items(client, setup, "bob"))[0]["reply_count"] == 2
    assert await comment_count(client, setup) == 3


@pytest.mark.anyio
async def test_a_link_to_a_pruned_comment_is_not_found(client, session):
    setup = await create_community_setup(session)
    gone = await post_comment(client, setup, subject="alice", content="Bye")
    await delete(client, setup, gone, "alice")

    res = await client.get(
        f"{API}/comments/{gone['id']}/context",
        params={"thread_id": "anime:1"},
        headers=headers(setup),
    )
    assert res.status_code == 404


@pytest.mark.anyio
async def test_batches_and_their_undo_keep_the_counts(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "boss", role="admin")
    root = await post_comment(client, setup, subject="alice", content="Root")
    parent = int(root["id"])
    for i in range(3):
        await post_comment(client, setup, subject="spammer", content=f"Spam {i}", source="bad.example",
                           parent_comment_id=parent)
    await post_comment(client, setup, subject="bob", content="Fine", parent_comment_id=parent)
    assert (await thread_items(client, setup))[0]["reply_count"] == 4

    done = await client.post(f"{MOD}/comments/batch", headers=mod(setup), json={"action": "hide", "source": "bad.example"})
    assert done.json()["changed"] == 3
    assert (await thread_items(client, setup))[0]["reply_count"] == 1
    assert await comment_count(client, setup) == 2
    assert (await replies(client, setup, root))["total"] == 1

    (entry,) = [
        item for item in (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
        if item["action"] == "hide_batch"
    ]
    undone = await client.post(f"{MOD}/batches/{entry['batch']['id']}/undo", headers=admin(setup))
    assert undone.status_code == 200, undone.text
    assert (await thread_items(client, setup))[0]["reply_count"] == 4
    assert await comment_count(client, setup) == 5


@pytest.mark.anyio
async def test_a_deleted_comment_names_nobody(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, subject="alice", content="Root")
    await post_comment(client, setup, subject="bob", content="Reply", parent_comment_id=int(root["id"]))

    deleted = await delete(client, setup, root, "alice")
    assert deleted["community_user"] is None
    assert deleted["community_user_id"] is None

    # Its author included, as on Reddit
    for viewer in (None, "bob", "alice"):
        (item,) = await thread_items(client, setup, viewer)
        assert item["status"] == "deleted"
        assert item["community_user"] is None
        assert item["community_user_id"] is None
        assert item["content"] == ""


@pytest.mark.anyio
async def test_staff_see_removed_comments_in_full(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, subject="alice", content="Root")
    removed = await post_comment(client, setup, subject="spammer", content="Spam", parent_comment_id=int(root["id"]))
    gone = await post_comment(client, setup, subject="bob", content="Bye", parent_comment_id=int(root["id"]))
    await hide(client, setup, removed["id"])
    await delete(client, setup, gone, "bob")

    # Even with nothing below it, with its text, author and reason
    listed = await client.get(
        f"{API}/comments",
        params={"thread_id": "anime:1", "parent_comment_id": int(root["id"])},
        headers=headers(setup, "mod", role="moderator"),
    )
    (item,) = listed.json()["items"]
    assert item["id"] == removed["id"]
    assert item["content"] == "Spam"
    assert item["community_user"]["external_user_id"] == "spammer"
    assert item["removal_reason"] == "Spam"

    # Nobody else does, and a deleted comment stays gone for staff too
    assert (await replies(client, setup, root, "bob"))["items"] == []

    context = await client.get(
        f"{API}/comments/{removed['id']}/context",
        params={"thread_id": "anime:1"},
        headers=headers(setup, "mod", role="moderator"),
    )
    assert context.status_code == 200
