# tests/integration/test_moderation_models.py

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.common import utc_now
from app.models.comment import Comment
from app.models.community_user import CommunityUser
from app.models.moderation import CommunityBan, ModerationAction
from app.models.report import CommentReport
from app.models.thread import Thread
from tests.factories import create_community_setup


async def seed(session):
    community = (await create_community_setup(session))["community"]
    author = CommunityUser(community_id=community.id, external_user_id="1", display_name="author")
    moderator = CommunityUser(community_id=community.id, external_user_id="2", display_name="mod")
    session.add_all([author, moderator])
    await session.flush()
    thread = Thread(community_id=community.id, unique_id="anime:1:ep:1")
    session.add(thread)
    await session.flush()
    comment = Comment(
        thread_id=thread.id,
        community_user_id=author.id,
        content="hello",
        source="anikoto",
        client="extension",
    )
    session.add(comment)
    await session.commit()
    return community, author, moderator, comment


async def test_a_person_can_report_a_comment_once(session):
    _, _, moderator, comment = await seed(session)
    session.add(CommentReport(comment_id=comment.id, reporter_community_user_id=moderator.id, reason="spam"))
    await session.commit()
    assert comment.source == "anikoto"

    session.add(CommentReport(comment_id=comment.id, reporter_community_user_id=moderator.id, reason="spam"))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_bans_can_be_permanent_or_timed_and_are_logged(session):
    community, author, moderator, comment = await seed(session)
    permanent = CommunityBan(community_id=community.id, community_user_id=author.id)
    timed = CommunityBan(
        community_id=community.id,
        community_user_id=author.id,
        expires_at=utc_now() + timedelta(days=7),
    )
    session.add_all(
        [
            permanent,
            timed,
            ModerationAction(
                community_id=community.id,
                moderator_community_user_id=moderator.id,
                action="ban_user",
                target_community_user_id=author.id,
                comment_id=comment.id,
            ),
        ]
    )
    await session.commit()
    assert permanent.expires_at is None and permanent.lifted_at is None
    assert timed.expires_at is not None
