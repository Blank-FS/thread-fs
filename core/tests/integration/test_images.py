# tests/integration/test_images.py

import pytest

from tests.factories import create_community_setup
from tests.integration.test_gifs import GIF
from tests.integration.test_moderation import API, headers, hide, post_comment, thread_items

IMAGE = {"url": "https://i.imgur.com/cat.png", "width": 640, "height": 480}


async def image_setup(session, *, gifs=False):
    setup = await create_community_setup(session)
    setup["community"].image_hosts = ["i.imgur.com"]
    if gifs:
        setup["community"].klipy_app_key = "klipy-test-key"
    await session.commit()
    return setup


@pytest.mark.anyio
async def test_a_comment_can_be_only_an_image_from_an_allowed_host(client, session):
    setup = await image_setup(session)

    posted = await post_comment(client, setup, content="", image=IMAGE)
    assert posted["image"] == IMAGE
    assert (await thread_items(client, setup))[0]["image"] == IMAGE


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/pixel.png",
        "http://i.imgur.com/cat.png",
        "https://x.i.imgur.com/cat.png",
        "https://i.imgur.com.evil.example/cat.png",
        "https://user@i.imgur.com/cat.png",
        "https://i.imgur.com:8443/cat.png",
    ],
)
async def test_images_only_from_the_communitys_hosts(client, session, url):
    setup = await image_setup(session)
    res = await client.post(
        f"{API}/comments",
        headers=headers(setup, "alice"),
        json={"thread_id": "anime:1", "content": "hi", "image": {**IMAGE, "url": url}},
    )
    assert res.status_code == 400, url


@pytest.mark.anyio
async def test_no_images_where_there_are_no_hosts(client, session):
    setup = await create_community_setup(session)
    res = await client.post(
        f"{API}/comments",
        headers=headers(setup, "alice"),
        json={"thread_id": "anime:1", "content": "hi", "image": IMAGE},
    )
    assert res.status_code == 400


@pytest.mark.anyio
async def test_a_gif_or_an_image_never_both(client, session):
    setup = await image_setup(session, gifs=True)
    res = await client.post(
        f"{API}/comments",
        headers=headers(setup, "alice"),
        json={"thread_id": "anime:1", "content": "hi", "gif": GIF, "image": IMAGE},
    )
    assert res.status_code == 422

    # Nor by editing an image into a comment that has a GIF
    posted = await post_comment(client, setup, content="Look", gif=GIF)
    url = f"{API}/comments/{posted['id']}"
    res = await client.patch(url, headers=headers(setup, "alice"), json={"content": "Look", "image": IMAGE})
    assert res.status_code == 422

    # Swapping one for the other is fine
    res = await client.patch(url, headers=headers(setup, "alice"), json={"content": "Look", "gif": None, "image": IMAGE})
    assert res.status_code == 200
    assert (res.json()["gif"], res.json()["image"]) == (None, IMAGE)


@pytest.mark.anyio
async def test_edits_keep_or_remove_the_image(client, session):
    setup = await image_setup(session)
    posted = await post_comment(client, setup, content="Look", image=IMAGE)
    url = f"{API}/comments/{posted['id']}"

    res = await client.patch(url, headers=headers(setup, "alice"), json={"content": "Look at this"})
    assert res.json()["image"] == IMAGE

    res = await client.patch(url, headers=headers(setup, "alice"), json={"content": "Just text", "image": None})
    assert res.json()["image"] is None


@pytest.mark.anyio
async def test_removed_and_deleted_comments_lose_the_image(client, session):
    setup = await image_setup(session)
    hidden = await post_comment(client, setup, content="", image=IMAGE)
    deleted = await post_comment(client, setup, subject="bob", content="", image=IMAGE)

    await hide(client, setup, hidden["id"])
    images = {item["id"]: item["image"] for item in await thread_items(client, setup, "carol")}
    assert images == {hidden["id"]: None, deleted["id"]: IMAGE}

    res = await client.delete(f"{API}/comments/{deleted['id']}", headers=headers(setup, "bob"))
    assert res.json()["image"] is None
