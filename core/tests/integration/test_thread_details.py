# tests/integration/test_thread_details.py

import pytest

from tests.factories import create_community_setup
from tests.helpers import create_test_token, embed_headers

API = "/api/v1/embed"
MOD = "/api/v1/moderation"
THREAD = "anime:1:ep:1"
REAL = {"id": THREAD, "title": "Frieren Episode 1", "url": "https://example.com/anime/1/episode/1"}


def headers(setup, subject="alice", claims=None, role=None):
    token = create_test_token(
        secret=setup["secret"], issuer=setup["issuer"], subject=subject, username=subject, claims=claims, role=role
    )
    return embed_headers(public_key=setup["public_key"], origin=setup["origin"], token=token)


def signed(thread=None):
    return {"threadfs_signed_threads": True, **({"threadfs_thread": thread} if thread else {})}


async def post(client, setup, claims=None, thread_id=THREAD, subject="alice", **body):
    return await client.post(
        f"{API}/comments",
        headers=headers(setup, subject, claims),
        json={"thread_id": thread_id, "content": "Hello", **body},
    )


async def stored(client, setup, thread_id=THREAD):
    res = await client.get(
        f"{MOD}/comments", params={"thread_id": thread_id}, headers=headers(setup, "mod", role="moderator")
    )
    items = res.json()["items"]
    return items[0]["thread"] if items else None


@pytest.mark.anyio
async def test_a_signed_thread_ignores_what_the_browser_sends(client, session):
    setup = await create_community_setup(session)

    res = await post(client, setup, signed(REAL), title="Free coins", source_url="https://evil.example/phish")
    assert res.status_code == 200, res.text

    thread = await stored(client, setup)
    assert thread["title"] == "Frieren Episode 1"
    assert thread["source_url"] == "https://example.com/anime/1/episode/1"


@pytest.mark.anyio
async def test_a_malicious_first_comment_can_not_set_the_link(client, session):
    setup = await create_community_setup(session)

    # A real token for this thread, but a forged request body
    await post(client, setup, signed(REAL), subject="mallory", title="Evil", source_url="https://evil.example/")
    await post(client, setup, signed(REAL), subject="alice")

    thread = await stored(client, setup)
    assert thread["source_url"] == REAL["url"]
    assert thread["title"] == REAL["title"]


@pytest.mark.anyio
async def test_a_signed_host_only_creates_threads_it_vouched_for(client, session):
    setup = await create_community_setup(session)

    assert (await post(client, setup, signed(), thread_id="made:up")).status_code == 404
    other = {**REAL, "id": "anime:2"}
    assert (await post(client, setup, signed(other), thread_id="made:up")).status_code == 404
    assert await stored(client, setup, "made:up") is None


@pytest.mark.anyio
async def test_comments_still_work_on_an_existing_thread_without_a_matching_claim(client, session):
    setup = await create_community_setup(session)
    await post(client, setup, signed(REAL))

    res = await post(client, setup, signed(), title="Evil", source_url="https://evil.example/")
    assert res.status_code == 200, res.text

    thread = await stored(client, setup)
    assert thread["title"] == REAL["title"]
    assert thread["source_url"] == REAL["url"]


@pytest.mark.anyio
async def test_a_signed_claim_repairs_a_bad_stored_link(client, session):
    setup = await create_community_setup(session)
    await post(client, setup, None, title="Old page title", source_url=f"{setup['origin']}/embed/anime/1/episode/1")

    await post(client, setup, signed(REAL))

    thread = await stored(client, setup)
    assert thread["source_url"] == REAL["url"]
    assert thread["title"] == REAL["title"]


@pytest.mark.anyio
async def test_an_unsigned_host_keeps_only_links_to_its_own_sites(client, session):
    setup = await create_community_setup(session)
    origin = setup["origin"]

    await post(client, setup, None, thread_id="own", title="Own", source_url=f"{origin}/own")
    assert (await stored(client, setup, "own"))["source_url"] == f"{origin}/own"

    for thread_id, url in (
        ("elsewhere", "https://evil.example/phish"),
        ("script", "javascript:alert(1)"),
        ("relative", "/just/a/path"),
    ):
        assert (await post(client, setup, None, thread_id=thread_id, source_url=url)).status_code == 200
        assert (await stored(client, setup, thread_id))["source_url"] is None


@pytest.mark.anyio
async def test_an_unsigned_commenter_can_not_change_an_existing_thread(client, session):
    setup = await create_community_setup(session)
    origin = setup["origin"]
    await post(client, setup, None, title="First", source_url=f"{origin}/first")

    await post(client, setup, None, subject="bob", title="Second", source_url=f"{origin}/second")

    thread = await stored(client, setup)
    assert thread["title"] == "First"
    assert thread["source_url"] == f"{origin}/first"


@pytest.mark.anyio
async def test_a_forged_claim_is_refused(client, session):
    setup = await create_community_setup(session)
    forged = create_test_token(
        secret="not-the-secret", issuer=setup["issuer"], subject="mallory", claims=signed(REAL)
    )

    res = await client.post(
        f"{API}/comments",
        headers=embed_headers(public_key=setup["public_key"], origin=setup["origin"], token=forged),
        json={"thread_id": THREAD, "content": "Hello"},
    )
    assert res.status_code == 401
    assert await stored(client, setup) is None


@pytest.mark.anyio
async def test_any_signed_in_request_keeps_the_avatar_up_to_date(client, session):
    setup = await create_community_setup(session)

    async def me(**token_args):
        token = create_test_token(secret=setup["secret"], issuer=setup["issuer"], subject="alice", **token_args)
        res = await client.get(
            f"{API}/me",
            headers=embed_headers(public_key=setup["public_key"], origin=setup["origin"], token=token),
        )
        assert res.status_code == 200, res.text
        return res.json()["avatar_url"]

    assert await me(avatar_url="https://example.com/a.png") == "https://example.com/a.png"
    assert await me(avatar_url="https://example.com/b.png") == "https://example.com/b.png"
    # Saying nothing leaves it, and saying there's none clears it
    assert await me(omit_avatar=True) == "https://example.com/b.png"
    assert await me(avatar_url=None) is None
