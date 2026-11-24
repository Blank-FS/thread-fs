# tests/integration/test_shared_reads.py
"""What readers share between requests (app.core.ttl_cache), which the other tests run without."""

import asyncio

import pytest

from app.api.routes import embed
from app.core.ttl_cache import TTLCache
from app.services import comment_page_service, community_context
from tests.factories import create_community_setup
from tests.integration.test_moderation import MOD, API, admin, headers, hide, mod, post_comment


@pytest.fixture
def shared(monkeypatch):
    caches = [embed._signed_out_reads, comment_page_service._shared_pages, community_context._cache]
    for cache in caches:
        monkeypatch.setattr(cache, "seconds", 60)
    yield
    for cache in caches:
        cache.clear()


async def contents(client, setup, subject=None, sign=headers, **params):
    res = await client.get(
        f"{API}/comments", params={"thread_id": "anime:1", "reply_preview": 2, **params}, headers=sign(setup, subject)
    )
    assert res.status_code == 200, res.text
    return {item["content"]: item for item in res.json()["items"]}


async def vote(client, setup, comment, subject):
    res = await client.post(f"{API}/comments/{comment['id']}/votes", headers=headers(setup, subject), json={"value": 1})
    assert res.status_code == 200, res.text


@pytest.mark.anyio
async def test_callers_that_miss_at_once_share_one_load():
    cache = TTLCache(60, max_entries=10)
    loads = 0

    async def load():
        nonlocal loads
        loads += 1
        await asyncio.sleep(0.01)
        return loads

    assert await asyncio.gather(*(cache.get("key", load) for _ in range(20))) == [1] * 20
    assert await cache.get("key", load) == 1
    cache.clear()
    assert await cache.get("key", load) == 2


@pytest.mark.anyio
async def test_a_load_that_fails_isnt_remembered():
    cache = TTLCache(60, max_entries=10)

    async def fail():
        await asyncio.sleep(0.01)
        raise ValueError

    results = await asyncio.gather(*(cache.get("key", fail) for _ in range(3)), return_exceptions=True)
    assert all(isinstance(result, ValueError) for result in results)

    async def load():
        return "fine"

    assert await cache.get("key", load) == "fine"


@pytest.mark.anyio
async def test_a_cancelled_load_leaves_it_to_the_next():
    cache = TTLCache(60, max_entries=10)

    async def load():
        await asyncio.sleep(0.05)
        return "fine"

    first = asyncio.create_task(cache.get("key", load))
    await asyncio.sleep(0.01)
    second = asyncio.create_task(cache.get("key", load))
    await asyncio.sleep(0.01)
    first.cancel()

    assert await second == "fine"


@pytest.mark.anyio
async def test_the_least_recently_used_go_first():
    cache = TTLCache(60, max_entries=2)

    async def load():
        return object()

    a = await cache.get("a", load)
    await cache.get("b", load)
    assert await cache.get("a", load) is a
    await cache.get("c", load)
    assert await cache.get("a", load) is a


@pytest.mark.anyio
async def test_signed_out_readers_share_a_page(client, session, shared):
    setup = await create_community_setup(session)
    await post_comment(client, setup, content="First")
    assert set(await contents(client, setup)) == {"First"}

    await post_comment(client, setup, content="Second")

    assert set(await contents(client, setup)) == {"First"}
    embed._signed_out_reads.clear()
    assert set(await contents(client, setup)) == {"First", "Second"}


@pytest.mark.anyio
async def test_signed_in_viewers_share_a_page_but_not_votes(client, session, shared):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup, content="Root")
    reply = await post_comment(client, setup, content="Reply", parent_comment_id=int(root["id"]))
    await vote(client, setup, root, "bob")
    await vote(client, setup, reply, "carol")

    bob = (await contents(client, setup, "bob"))["Root"]
    carol = (await contents(client, setup, "carol"))["Root"]
    dave = (await contents(client, setup, "dave"))["Root"]

    assert (bob["viewer_vote"], bob["replies"][0]["viewer_vote"]) == (1, None)
    assert (carol["viewer_vote"], carol["replies"][0]["viewer_vote"]) == (None, 1)
    assert (dave["viewer_vote"], dave["replies"][0]["viewer_vote"]) == (None, None)
    assert len(comment_page_service._shared_pages._entries) == 1


@pytest.mark.anyio
async def test_signed_in_viewers_see_changes_at_once(client, session, shared):
    setup = await create_community_setup(session)
    first = await post_comment(client, setup, content="First")
    assert set(await contents(client, setup, "bob")) == {"First"}

    await post_comment(client, setup, content="Second")
    assert set(await contents(client, setup, "bob")) == {"First", "Second"}

    res = await client.patch(
        f"{API}/comments/{first['id']}", headers=headers(setup, "alice"), json={"content": "Edited"}
    )
    assert res.status_code == 200, res.text
    assert set(await contents(client, setup, "bob")) == {"Edited", "Second"}

    res = await client.delete(f"{API}/comments/{first['id']}", headers=headers(setup, "alice"))
    assert res.status_code == 200, res.text
    assert set(await contents(client, setup, "bob")) == {"Second"}


@pytest.mark.anyio
async def test_a_removed_comment_shows_only_to_its_author_and_staff(client, session, shared):
    setup = await create_community_setup(session)
    removed = await post_comment(client, setup, content="Removed")
    await post_comment(client, setup, subject="bob", content="Kept")
    assert set(await contents(client, setup, "carol")) == {"Removed", "Kept"}

    await hide(client, setup, removed["id"])

    assert set(await contents(client, setup, "carol")) == {"Kept"}
    assert set(await contents(client, setup, "alice")) == {"Removed", "Kept"}
    assert set(await contents(client, setup, "mod", sign=lambda setup, _: mod(setup))) == {"Removed", "Kept"}
    # And nobody's page was left for others to see
    assert set(await contents(client, setup, "dave")) == {"Kept"}


@pytest.mark.anyio
async def test_admin_settings_apply_at_once_where_they_were_made(client, session, shared):
    setup = await create_community_setup(session)

    async def config():
        return (await client.get(f"{API}/config", headers=headers(setup))).json()

    assert (await config())["rules_url"] is None
    for url in ("https://example.com/rules", None):
        res = await client.put(f"{MOD}/admin/rules", headers=admin(setup), json={"rules_url": url})
        assert res.status_code == 200, res.text
        assert (await config())["rules_url"] == url


@pytest.mark.anyio
async def test_an_unknown_key_isnt_remembered(client, session, shared):
    missing = {"Origin": "https://example.com", "X-ThreadFS-Community-Key": "tfspub_test"}
    assert (await client.get(f"{API}/config", headers=missing)).status_code == 404

    await create_community_setup(session)

    assert (await client.get(f"{API}/config", headers=missing)).status_code == 200
    # Nor does remembering it let in another origin
    wrong = {**missing, "Origin": "https://elsewhere.example"}
    assert (await client.get(f"{API}/config", headers=wrong)).status_code == 403
