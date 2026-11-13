# tests/integration/test_gifs.py

import pytest

from tests.factories import create_community_setup
from tests.integration.test_moderation import API, headers, hide, mod, post_comment, thread_items

GIF = {
    "provider": "klipy",
    "slug": "hello-hi-662",
    "url": "https://static.klipy.com/ii/abc/12/34/hello.webp",
    "width": 220,
    "height": 220,
    "title": "Hello",
}


async def gif_setup(session):
    setup = await create_community_setup(session)
    setup["community"].klipy_app_key = "klipy-test-key"
    await session.commit()
    return setup


@pytest.mark.anyio
async def test_config_offers_gifs_only_with_a_key(client, session):
    setup = await create_community_setup(session)
    res = await client.get(f"{API}/config", headers=headers(setup))
    assert res.json()["gifs"] is None

    setup["community"].klipy_app_key = "klipy-test-key"
    await session.commit()
    res = await client.get(f"{API}/config", headers=headers(setup))
    assert res.json()["gifs"] == {"provider": "klipy", "app_key": "klipy-test-key"}


@pytest.mark.anyio
async def test_a_comment_can_be_only_a_gif(client, session):
    setup = await gif_setup(session)

    posted = await post_comment(client, setup, content="", gif=GIF)
    assert posted["content"] == ""
    assert posted["gif"] == GIF
    assert (await thread_items(client, setup))[0]["gif"] == GIF


@pytest.mark.anyio
async def test_a_comment_needs_text_or_a_gif(client, session):
    setup = await gif_setup(session)
    for content in ("", "   ", "<script>x</script>"):
        res = await client.post(
            f"{API}/comments",
            headers=headers(setup, "alice"),
            json={"thread_id": "anime:1", "content": content},
        )
        assert res.status_code == 422, content


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/pixel.gif",
        "http://static.klipy.com/ii/a.gif",
        "https://static.klipy.com.evil.example/a.gif",
        "https://user@static.klipy.com/a.gif",
        "javascript:alert(1)",
    ],
)
async def test_only_klipy_files_are_accepted(client, session, url):
    setup = await gif_setup(session)
    res = await client.post(
        f"{API}/comments",
        headers=headers(setup, "alice"),
        json={"thread_id": "anime:1", "content": "hi", "gif": {**GIF, "url": url}},
    )
    assert res.status_code == 422


@pytest.mark.anyio
async def test_gifs_are_refused_where_they_are_off(client, session):
    setup = await create_community_setup(session)
    res = await client.post(
        f"{API}/comments",
        headers=headers(setup, "alice"),
        json={"thread_id": "anime:1", "content": "hi", "gif": GIF},
    )
    assert res.status_code == 400


@pytest.mark.anyio
async def test_edits_keep_change_or_remove_the_gif(client, session):
    setup = await gif_setup(session)
    posted = await post_comment(client, setup, content="Look", gif=GIF)
    url = f"{API}/comments/{posted['id']}"

    # Left out: kept, so a client that doesn't know about GIFs can't drop one
    res = await client.patch(url, headers=headers(setup, "alice"), json={"content": "Look at this"})
    assert res.json()["gif"] == GIF

    other = {**GIF, "slug": "wave-1", "url": "https://static1.klipy.com/ii/def/wave.webp"}
    res = await client.patch(url, headers=headers(setup, "alice"), json={"content": "Look", "gif": other})
    assert res.json()["gif"] == other

    res = await client.patch(url, headers=headers(setup, "alice"), json={"content": "Just text", "gif": None})
    assert res.json()["gif"] is None

    # Nothing left: refused
    res = await client.patch(url, headers=headers(setup, "alice"), json={"content": "", "gif": None})
    assert res.status_code == 422


@pytest.mark.anyio
async def test_removed_and_deleted_comments_lose_the_gif(client, session):
    setup = await gif_setup(session)
    hidden = await post_comment(client, setup, content="", gif=GIF)
    deleted = await post_comment(client, setup, subject="bob", content="", gif=GIF)
    # A reply keeps the removed comment in the thread for everyone
    await post_comment(client, setup, subject="dave", content="Reply", parent_comment_id=int(hidden["id"]))

    await hide(client, setup, hidden["id"])
    gifs = {item["id"]: item["gif"] for item in await thread_items(client, setup, "carol")}
    assert gifs == {hidden["id"]: None, deleted["id"]: GIF}
    # Moderators still see what was removed
    res = await client.get(f"/api/v1/moderation/comments", headers=mod(setup), params={"status": "hidden"})
    assert res.json()["items"][0]["gif"] == GIF

    res = await client.delete(f"{API}/comments/{deleted['id']}", headers=headers(setup, "bob"))
    assert res.json()["gif"] is None
