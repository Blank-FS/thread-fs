# app/db/init_db.py

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine, async_session_maker
from app.models.community import Community
from app.models.community_allowed_origin import CommunityAllowedOrigin
from app.models.community_api_key import CommunityApiKey
from app.models.community_auth_provider import CommunityAuthProvider
from app.models.user import User
from app.models.community_user import CommunityUser
from app.models.thread import Thread
from app.models.comment import Comment
from app.core.common import utc_now


async def drop_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def create_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def reset_db() -> None:
    await drop_db()
    await create_db()


async def seed_db() -> None:
    async with async_session_maker() as session:
        await seed_demo_data(session)
        await seed_demo_comments(session)


async def seed_demo_data(session: AsyncSession) -> None:
    existing = await session.execute(
        select(Community).where(Community.slug == "demo-community")
    )

    if existing.scalar_one_or_none():
        return

    demo_user = User(
        id=uuid.uuid4(),
        email="demo-owner@threadfs.dev",
        hashed_password="not-a-real-password",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )

    session.add(demo_user)
    await session.flush()

    community = Community(
        name="Demo Community",
        slug="demo-community",
        description="Local development community for ThreadFS.",
        site_url="http://localhost:3000",
        user_id=demo_user.id,
        allow_anonymous_read=True,
        allow_anonymous_comment=False,
    )

    session.add(community)
    await session.flush()

    auth_provider = CommunityAuthProvider(
        community_id=community.id,
        issuer="demo-site",
        algorithm="HS256",
        secret="dev-threadfs-secret",
        audience="threadfs",
    )

    session.add(auth_provider)

    api_key = CommunityApiKey(
        community_id=community.id,
        public_key="tfspub_demo_abc123",
        secret_hash="dev-secret-hash-not-for-production",
    )

    session.add(api_key)

    origins = [
        CommunityAllowedOrigin(
            community_id=community.id,
            origin="http://localhost:3000",
        ),
        CommunityAllowedOrigin(
            community_id=community.id,
            origin="http://localhost:5173",
        ),
    ]

    session.add_all(origins)

    await session.commit()


async def seed_demo_comments(session: AsyncSession) -> None:
    community = await _get_demo_community(session)
    if not community:
        return

    # Avoid duplicating comments every restart if you are not dropping tables.
    existing_thread = await session.execute(
        select(Thread).where(
            Thread.community_id == community.id,
            Thread.unique_id == "demo-thread",
        )
    )
    thread = existing_thread.scalar_one_or_none()

    if thread:
        return

    now = utc_now()

    users = await _seed_demo_community_users(session, community.id)

    thread = Thread(
        community_id=community.id,
        unique_id="demo-thread",
        title="Demo Thread",
        source_url="http://localhost:3000/demo",
        comment_count=0,
        created_at=now - timedelta(days=2),
        modified_at=now - timedelta(days=2),
    )
    session.add(thread)
    await session.flush()

    top_level_specs = [
        {
            "author": 0,
            "minutes_ago": 5,
            "content": "<p>Newest comment. This should appear first when sorted by latest.</p>",
            "up": 1,
            "down": 0,
        },
        {
            "author": 1,
            "minutes_ago": 15,
            "content": "<p>Recent comment with a few votes.</p>",
            "up": 4,
            "down": 1,
        },
        {
            "author": 2,
            "minutes_ago": 45,
            "content": "<p>Another recent top-level comment.</p>",
            "up": 2,
            "down": 0,
        },
        {
            "author": 3,
            "minutes_ago": 90,
            "content": "<p>This one is useful for page one/page two boundaries.</p>",
            "up": 8,
            "down": 2,
        },
        {
            "author": 0,
            "minutes_ago": 150,
            "content": "<p>Older comment with medium score.</p>",
            "up": 6,
            "down": 1,
        },
        {
            "author": 1,
            "minutes_ago": 240,
            "content": "<p>Old comment. Should move down in latest sorting.</p>",
            "up": 0,
            "down": 0,
        },
        {
            "author": 2,
            "minutes_ago": 360,
            "content": "<p>High score comment. Should rank highly in top sort.</p>",
            "up": 20,
            "down": 3,
        },
        {
            "author": 3,
            "minutes_ago": 480,
            "content": "<p>Controversial comment with many downvotes.</p>",
            "up": 7,
            "down": 9,
        },
        {
            "author": 0,
            "minutes_ago": 720,
            "content": "<p>Yesterday-ish comment.</p>",
            "up": 3,
            "down": 0,
        },
        {
            "author": 1,
            "minutes_ago": 900,
            "content": "<p>Another older comment for pagination testing.</p>",
            "up": 5,
            "down": 5,
        },
        {
            "author": 2,
            "minutes_ago": 1200,
            "content": "<p>Old but very popular comment. Should be near top for top sort.</p>",
            "up": 30,
            "down": 4,
        },
        {
            "author": 3,
            "minutes_ago": 1500,
            "content": "<p>Oldest seeded top-level comment. Should appear first in oldest sort.</p>",
            "up": 1,
            "down": 0,
        },
    ]

    top_comments: list[Comment] = []

    for spec in top_level_specs:
        created_at = now - timedelta(minutes=spec["minutes_ago"])

        comment = Comment(
            thread_id=thread.id,
            parent_comment_id=None,
            community_user_id=users[spec["author"]].id,
            content=spec["content"],
            status="visible",
            upvote_count=spec["up"],
            downvote_count=spec["down"],
            reply_count=0,
            created_at=created_at,
            modified_at=created_at,
        )
        session.add(comment)
        top_comments.append(comment)

    await session.flush()

    # Add replies to a few top-level comments.
    await _seed_replies_for_parent(
        session,
        parent=top_comments[0],
        users=users,
        count=7,
        start_minutes_ago=4,
        interval_minutes=1,
    )

    await _seed_replies_for_parent(
        session,
        parent=top_comments[3],
        users=users,
        count=5,
        start_minutes_ago=80,
        interval_minutes=5,
    )

    await _seed_replies_for_parent(
        session,
        parent=top_comments[6],
        users=users,
        count=9,
        start_minutes_ago=300,
        interval_minutes=10,
    )

    thread.comment_count = await _count_all_thread_comments(session, thread.id)

    await session.commit()


async def _get_demo_community(session: AsyncSession) -> Community | None:
    result = await session.execute(
        select(Community).where(Community.name == "Demo Community")
    )
    return result.scalar_one_or_none()


async def _seed_demo_community_users(
    session: AsyncSession,
    community_id: uuid.UUID,
) -> list[CommunityUser]:
    existing = await session.execute(
        select(CommunityUser).where(CommunityUser.community_id == community_id)
    )
    users = list(existing.scalars().all())

    if len(users) >= 4:
        return users[:4]

    demo_users = [
        {
            "external_user_id": "demo-user-1",
            "display_name": "Blank",
            "avatar_url": "https://api.dicebear.com/8.x/initials/svg?seed=Blank",
        },
        {
            "external_user_id": "demo-user-2",
            "display_name": "Sora",
            "avatar_url": "https://api.dicebear.com/8.x/initials/svg?seed=Sora",
        },
        {
            "external_user_id": "demo-user-3",
            "display_name": "Shiro",
            "avatar_url": "https://api.dicebear.com/8.x/initials/svg?seed=Shiro",
        },
        {
            "external_user_id": "demo-user-4",
            "display_name": "Violet",
            "avatar_url": "https://api.dicebear.com/8.x/initials/svg?seed=Violet",
        },
    ]

    for user_data in demo_users[len(users) :]:
        user = CommunityUser(
            community_id=community_id,
            identity_provider="external",
            external_user_id=user_data["external_user_id"],
            display_name=user_data["display_name"],
            avatar_url=user_data["avatar_url"],
        )
        session.add(user)
        users.append(user)

    await session.flush()
    return users


async def _seed_replies_for_parent(
    session: AsyncSession,
    *,
    parent: Comment,
    users: list[CommunityUser],
    count: int,
    start_minutes_ago: int,
    interval_minutes: int,
) -> None:
    now = utc_now()

    for index in range(count):
        created_at = now - timedelta(
            minutes=start_minutes_ago - index * interval_minutes
        )

        reply = Comment(
            thread_id=parent.thread_id,
            parent_comment_id=parent.id,
            community_user_id=users[index % len(users)].id,
            content=f"<p>Reply {index + 1} to comment {parent.id}. Replies should sort oldest first.</p>",
            status="visible",
            upvote_count=index % 4,
            downvote_count=0,
            reply_count=0,
            created_at=created_at,
            modified_at=created_at,
        )
        session.add(reply)

    parent.reply_count += count
    await session.flush()


async def _count_all_thread_comments(session: AsyncSession, thread_id: int) -> int:
    from sqlalchemy import func

    result = await session.execute(
        select(func.count(Comment.id)).where(Comment.thread_id == thread_id)
    )

    return int(result.scalar_one())
