# tests/integration/test_origin_validation.py

import pytest

from tests.factories import create_community_setup
from tests.helpers import embed_headers


@pytest.mark.anyio
async def test_rejects_disallowed_origin(client, session):
    setup = await create_community_setup(session)

    res = await client.get(
        "/api/v1/embed/comments",
        params={"thread_id": "test"},
        headers=embed_headers(
            public_key=setup["public_key"],
            origin="https://evil.example",
        ),
    )

    assert res.status_code == 403
