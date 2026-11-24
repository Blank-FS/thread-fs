# tests/integration/test_concurrency.py
"""Requests at the same time: nothing is lost, and nothing is created twice."""

import asyncio

import pytest
from sqlalchemy import func, select

from app.models.comment import Comment
from app.models.community_user import CommunityUser
from app.models.thread import Thread
from tests.conftest import TestSessionLocal
from tests.factories import create_community_setup
from tests.integration.test_moderation import API, headers, post_comment


async def scalar(statement):
    """One value as the database has it now."""
    async with TestSessionLocal() as session:
        return (await session.execute(statement)).scalar_one()


def stored(comment):
    return scalar(select(Comment).where(Comment.id == int(comment["id"])))


@pytest.mark.anyio
async def test_votes_at_once_all_count(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    voters = [f"voter-{n}" for n in range(12)]
    for voter in voters:
        await client.get(f"{API}/me", headers=headers(setup, voter))

    results = await asyncio.gather(
        *(
            client.post(f"{API}/comments/{comment['id']}/votes", headers=headers(setup, voter), json={"value": 1})
            for voter in voters
        )
    )

    assert [res.status_code for res in results] == [200] * 12
    assert (await stored(comment)).upvote_count == 12


@pytest.mark.anyio
async def test_the_same_vote_twice_at_once_toggles_rather_than_failing(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    await client.get(f"{API}/me", headers=headers(setup, "bob"))

    results = await asyncio.gather(
        *(
            client.post(f"{API}/comments/{comment['id']}/votes", headers=headers(setup, "bob"), json={"value": 1})
            for _ in range(2)
        )
    )

    assert [res.status_code for res in results] == [200] * 2
    assert (await stored(comment)).upvote_count == 0


@pytest.mark.anyio
async def test_replies_at_once_all_count(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup)
    middle = await post_comment(client, setup, parent_comment_id=int(root["id"]))
    people = [f"person-{n}" for n in range(12)]
    for person in people:
        await client.get(f"{API}/me", headers=headers(setup, person))

    # At two depths of one chain, so they lock the same rows
    await asyncio.gather(
        *(
            post_comment(
                client, setup, subject=person, parent_comment_id=int((root if n % 2 else middle)["id"])
            )
            for n, person in enumerate(people)
        )
    )

    assert (await stored(root)).reply_count == 13
    assert (await stored(middle)).reply_count == 6
    assert await scalar(select(Thread.comment_count)) == 14


@pytest.mark.anyio
async def test_replying_while_the_parent_is_deleted_never_deadlocks(client, session):
    setup = await create_community_setup(session)
    root = await post_comment(client, setup)
    middles = [
        await post_comment(client, setup, subject=f"owner-{n}", parent_comment_id=int(root["id"])) for n in range(4)
    ]
    for n in range(4):
        await client.get(f"{API}/me", headers=headers(setup, f"person-{n}"))

    def reply(n, middle):
        return client.post(
            f"{API}/comments",
            headers=headers(setup, f"person-{n}"),
            json={"thread_id": "anime:1", "content": "Hi", "parent_comment_id": int(middle["id"])},
        )

    results = await asyncio.gather(
        *(reply(n, middle) for n, middle in enumerate(middles)),
        *(
            client.delete(f"{API}/comments/{middle['id']}", headers=headers(setup, f"owner-{n}"))
            for n, middle in enumerate(middles)
        ),
    )

    # A reply to one already deleted is refused, and that's the only way any of these may fail
    assert {res.status_code for res in results} <= {200, 404}
    visible = await scalar(select(func.count(Comment.id)).where(Comment.status == "visible"))
    assert await scalar(select(Thread.comment_count)) == visible


@pytest.mark.anyio
async def test_first_requests_at_once_create_one_user(client, session):
    setup = await create_community_setup(session)

    results = await asyncio.gather(
        *(client.get(f"{API}/me", headers=headers(setup, "newcomer")) for _ in range(8))
    )

    assert {res.status_code for res in results} == {200}
    assert len({res.json()["community_user_id"] for res in results}) == 1
    assert await scalar(select(func.count(CommunityUser.id))) == 1
