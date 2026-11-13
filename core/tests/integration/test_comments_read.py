# tests/integration/test_comments_read.py

import pytest

from tests.factories import create_community_setup
from tests.helpers import embed_headers


@pytest.mark.anyio
async def test_missing_thread_returns_empty_page(client, session):
    setup = await create_community_setup(session)

    res = await client.get(
        "/api/v1/embed/comments",
        params={"thread_id": "missing-thread"},
        headers=embed_headers(
            public_key=setup["public_key"],
            origin=setup["origin"],
        ),
    )

    assert res.status_code == 200

    body = res.json()
    assert body["items"] == []
    assert body["has_more"] is False
    assert body["next_offset"] is None
    assert body["total"] == 0


@pytest.mark.anyio
async def test_my_comments_say_who_each_reply_answers(client, session):
    from tests.integration.test_moderation import API, headers, hide, post_comment

    setup = await create_community_setup(session)
    root = await post_comment(client, setup, subject="mira", content="Root")
    removed = await post_comment(client, setup, subject="spammer", content="Spam")
    gone = await post_comment(client, setup, subject="leaver", content="Bye")

    top = await post_comment(client, setup, subject="alice", content="Top level")
    reply = await post_comment(client, setup, subject="alice", content="To Mira", parent_comment_id=int(root["id"]))
    to_removed = await post_comment(client, setup, subject="alice", content="To spam", parent_comment_id=int(removed["id"]))
    to_deleted = await post_comment(client, setup, subject="alice", content="To gone", parent_comment_id=int(gone["id"]))

    await hide(client, setup, removed["id"])
    await client.delete(f"{API}/comments/{gone['id']}", headers=headers(setup, "leaver"))

    res = await client.get(f"{API}/comments/mine", headers=headers(setup, "alice"))
    assert res.status_code == 200
    replying = {item["id"]: item["replying_to"] for item in res.json()["items"]}

    assert replying[top["id"]] is None
    assert replying[reply["id"]] == {"status": "visible", "display_name": "mira", "external_user_id": "mira"}
    # Withheld, as in the thread
    assert replying[to_removed["id"]] == {"status": "hidden", "display_name": None, "external_user_id": None}
    assert replying[to_deleted["id"]] == {"status": "deleted", "display_name": None, "external_user_id": None}
