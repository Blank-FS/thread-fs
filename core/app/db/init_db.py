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
from app.core.config import settings
from app.models.webhook import CommunityWebhook
from app.services.webhook_service import ALL_EVENTS, DEMO_SECRET


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

    # A webhook for trying them locally, when DEMO_WEBHOOK_URL is set (app.scripts.webhook_listener)
    if settings.DEMO_WEBHOOK_URL:
        session.add(
            CommunityWebhook(
                community_id=community.id,
                url=settings.DEMO_WEBHOOK_URL,
                secret=DEMO_SECRET,
                events=",".join(ALL_EVENTS),
                is_enabled=True,
            )
        )

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
            origin="http://localhost:3001",
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
        source_url="http://localhost:5173",
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
            "content": "Newest comment. This should appear first when sorted by latest.",
            "up": 1,
            "down": 0,
        },
        {
            "author": 1,
            "minutes_ago": 15,
            "content": "Recent comment with a few votes.",
            "up": 4,
            "down": 1,
        },
        {
            "author": 2,
            "minutes_ago": 45,
            "content": "Another recent top-level comment.",
            "up": 2,
            "down": 0,
        },
        {
            "author": 3,
            "minutes_ago": 90,
            "content": "This one is useful for page one/page two boundaries.",
            "up": 8,
            "down": 2,
        },
        {
            "author": 0,
            "minutes_ago": 150,
            "content": "Older comment with medium score.",
            "up": 6,
            "down": 1,
        },
        {
            "author": 1,
            "minutes_ago": 240,
            "content": "Old comment. Should move down in latest sorting.",
            "up": 0,
            "down": 0,
        },
        {
            "author": 2,
            "minutes_ago": 360,
            "content": "High score comment. Should rank highly in top sort.",
            "up": 20,
            "down": 3,
        },
        {
            "author": 3,
            "minutes_ago": 480,
            "content": "Controversial comment with many downvotes.",
            "up": 7,
            "down": 9,
        },
        {
            "author": 0,
            "minutes_ago": 720,
            "content": "Yesterday-ish comment.",
            "up": 3,
            "down": 0,
        },
        {
            "author": 1,
            "minutes_ago": 900,
            "content": "Another older comment for pagination testing.",
            "up": 5,
            "down": 5,
        },
        {
            "author": 2,
            "minutes_ago": 1200,
            "content": "Old but very popular comment. Should be near top for top sort.",
            "up": 30,
            "down": 4,
        },
        {
            "author": 3,
            "minutes_ago": 1500,
            "content": "Oldest seeded top-level comment. Should appear first in oldest sort.",
            "up": 1,
            "down": 0,
        },
        {
            "author": 4,
            "minutes_ago": 1,
            "content": "No avatar of my own, so I get the default one.",
            "up": 2,
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

    await _seed_nested_replies(session, thread=thread, users=users)

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

    if len(users) >= 5:
        return users[:5]

    demo_users = [
        {
            "external_user_id": "demo-user-1",
            "display_name": "Blank",
            "avatar_url": "https://api.dicebear.com/8.x/initials/svg?seed=Blank",
            # Served by the demo site, like the one in make_demo_token's token for Blank
            "avatar_frame_url": "http://localhost:5173/demo-frame.webp",
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
        {
            "external_user_id": "demo-user-5",
            "display_name": "Nova",
            "avatar_url": None,
        },
    ]

    for user_data in demo_users[len(users) :]:
        user = CommunityUser(
            community_id=community_id,
            identity_provider="external",
            external_user_id=user_data["external_user_id"],
            display_name=user_data["display_name"],
            avatar_url=user_data["avatar_url"],
            avatar_frame_url=user_data.get("avatar_frame_url"),
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
            content=f"Reply {index + 1} to comment {parent.id}. Replies should sort oldest first.",
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


# For seeing how deep threads behave, especially on a phone: short and long text, and things that can't wrap
NESTED_REPLIES = [
    "Level 1. Short replies should stay tidy.",
    "Level 2. A longer one, to see how a paragraph wraps once the column starts to narrow. "
    "It has a few sentences, like the replies people actually write when they disagree about an ending.",
    "Level 3. Agreed.",
    "Level 4. A long link: https://example.com/articles/2026/a-rather-long-article-title/comments?sort=top&from=notification",
    "Level 5. `inline code` and a block:\n\n```\nconst deeplyNestedValue = thread.replies[0].replies[0].replies[0];\n```",
    "Level 6. Averyveryveryveryveryveryveryveryveryveryveryveryveryverylongwordwithnospaces",
    "Level 7. Another paragraph, now that the indent has built up. If the column is too narrow by this point, "
    "it will take a lot of lines and be tiring to read.",
    "Level 8. Still going.",
    "Level 9. Is this still readable?",
    "Level 10. A last long one, to compare with level 2 and see how much width has been lost along the way.",
    "Level 11. Nearly there.",
    "Level 12. The bottom of the thread.",
]


async def _seed_nested_replies(
    session: AsyncSession,
    *,
    thread: Thread,
    users: list[CommunityUser],
) -> None:
    now = utc_now()
    parent = Comment(
        thread_id=thread.id,
        parent_comment_id=None,
        community_user_id=users[0].id,
        content="Nested replies test: this one goes 12 levels deep. Open each level to see how it behaves.",
        status="visible",
        upvote_count=3,
        downvote_count=0,
        reply_count=0,
        created_at=now,
        modified_at=now,
    )
    session.add(parent)
    await session.flush()

    # reply_count counts every reply below a comment, as creating one through the API does, so each new level adds one
    # to every comment above it
    chain = [parent]
    for index, content in enumerate(NESTED_REPLIES):
        reply = Comment(
            thread_id=thread.id,
            parent_comment_id=parent.id,
            community_user_id=users[(index + 1) % len(users)].id,
            content=content,
            status="visible",
            upvote_count=index % 3,
            downvote_count=0,
            reply_count=0,
            created_at=now,
            modified_at=now,
        )
        session.add(reply)
        await session.flush()
        for ancestor in chain:
            ancestor.reply_count += 1
        chain.append(reply)
        parent = reply


async def _count_all_thread_comments(session: AsyncSession, thread_id: int) -> int:
    from sqlalchemy import func

    result = await session.execute(
        select(func.count(Comment.id)).where(Comment.thread_id == thread_id)
    )

    return int(result.scalar_one())
