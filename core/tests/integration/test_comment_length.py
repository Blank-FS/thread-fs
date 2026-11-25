# tests/integration/test_comment_length.py

import pytest

from app.core.config import settings
from tests.factories import create_community_setup
from tests.integration.test_moderation import API, headers, post_comment


@pytest.mark.anyio
async def test_a_comment_can_be_as_long_as_the_config_says(client, session):
    setup = await create_community_setup(session)
    config = (await client.get(f"{API}/config", headers=headers(setup))).json()
    limit = config["max_comment_length"]
    assert limit == settings.MAX_COMMENT_LENGTH

    # Characters, not bytes: an emoji is one
    comment = await post_comment(client, setup, content="🙂" * limit)
    assert len(comment["content"]) == limit

    for method, path in (("POST", "/comments"), ("PATCH", f"/comments/{comment['id']}")):
        res = await client.request(
            method, f"{API}{path}", headers=headers(setup, "alice"), json={"thread_id": "anime:1", "content": "x" * (limit + 1)}
        )
        assert res.status_code == 422
        assert "10000" in res.json()["detail"][0]["msg"]
