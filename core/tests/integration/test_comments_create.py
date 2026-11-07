# tests/integration/test_comments_create.py

import pytest

from tests.factories import create_community_setup
from tests.helpers import create_test_token, embed_headers


@pytest.mark.anyio
async def test_create_first_comment_creates_thread(client, session):
    setup = await create_community_setup(session)

    token = create_test_token(
        secret=setup["secret"],
        issuer=setup["issuer"],
        subject="aniworks-user-1",
        username="Sora",
    )

    res = await client.post(
        "/api/v1/embed/comments",
        headers=embed_headers(
            public_key=setup["public_key"],
            origin=setup["origin"],
            token=token,
        ),
        json={
            "thread_id": "anime:1",
            "title": "Anime 1",
            "source_url": "https://example.com/anime/1",
            "content": "<p>Hello ThreadFS</p>",
            "parent_comment_id": None,
        },
    )

    assert res.status_code == 200 or res.status_code == 201

    body = res.json()
    assert body["content"] == "<p>Hello ThreadFS</p>"
    assert body["parent_comment_id"] is None
    assert body["upvote_count"] == 0
    assert body["downvote_count"] == 0
