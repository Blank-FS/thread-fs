# tests/integration/test_bootstrap.py

import pytest

from tests.factories import create_community_setup
from tests.integration.test_moderation import API, headers, post_comment


async def bootstrap(client, setup, subject=None, **payload):
    return await client.post(
        f"{API}/bootstrap",
        headers=headers(setup, subject),
        json={"thread_id": "anime:1", **payload},
    )


@pytest.mark.anyio
async def test_bootstrap_matches_the_separate_endpoints(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, content="Root")
    reply = await post_comment(client, setup, subject="bob", content="Reply", parent_comment_id=int(root["id"]))

    for subject in (None, "alice"):
        res = await bootstrap(client, setup, subject, reply_preview=2, comment_id=int(reply["id"]))
        assert res.status_code == 200, res.text
        body = res.json()

        async def get(path, **params):
            return (await client.get(f"{API}{path}", params=params, headers=headers(setup, subject))).json()

        assert body["config"] == await get("/config")
        assert body["me"] == await get("/me")
        assert body["comments"] == await get("/comments", thread_id="anime:1", limit=20, reply_preview=2)
        assert body["context"] == await get(f"/comments/{reply['id']}/context", thread_id="anime:1")
        resolved = await client.post(
            f"{API}/threads/resolve", headers=headers(setup, subject), json={"thread_id": "anime:1"}
        )
        assert body["thread"] == resolved.json()["thread"]


@pytest.mark.anyio
async def test_bootstrap_of_a_thread_nobody_commented_in(client, session):
    setup = await create_community_setup(session)

    body = (await bootstrap(client, setup)).json()

    assert body["thread"] is None
    assert body["comments"]["items"] == []
    assert body["me"]["authenticated"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("missing", [999_999, 0, 2**31, 2**60])
async def test_a_linked_comment_thats_gone_leaves_the_thread(client, session, missing):
    setup = await create_community_setup(session)
    await post_comment(client, setup, content="Root")

    res = await bootstrap(client, setup, comment_id=missing)

    assert res.status_code == 200, res.text
    assert res.json()["context"] is None
    assert len(res.json()["comments"]["items"]) == 1


@pytest.mark.anyio
async def test_bootstrap_needs_a_login_where_reading_does(client, session):
    setup = await create_community_setup(session, allow_anonymous_read=False)

    assert (await bootstrap(client, setup)).status_code == 401
    assert (await bootstrap(client, setup, "alice")).status_code == 200
