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
