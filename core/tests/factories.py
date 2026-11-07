import uuid
from datetime import datetime, timezone

from app.models.user import User
from app.models.community import Community
from app.models.community_api_key import CommunityApiKey
from app.models.community_allowed_origin import CommunityAllowedOrigin
from app.models.community_auth_provider import CommunityAuthProvider


def utc_now():
    return datetime.now(timezone.utc)


async def create_owner(session, *, email="owner@example.com"):
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="test-password",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )

    session.add(user)
    await session.flush()
    return user


async def create_community_setup(
    session,
    *,
    name="Test Community",
    slug="test-community",
    public_key="tfspub_test",
    origin="https://example.com",
    issuer="example-site",
    secret="test-secret",
    allow_anonymous_read=True,
    owner_email="owner@example.com",
):
    owner = await create_owner(session, email=owner_email)

    community = Community(
        user_id=owner.id,
        name=name,
        slug=slug,
        description="Test community",
        thread_count=0,
        allow_anonymous_read=allow_anonymous_read,
    )
    session.add(community)
    await session.flush()

    api_key = CommunityApiKey(
        community_id=community.id, public_key=public_key, secret_hash="secret_hash"
    )
    session.add(api_key)

    allowed_origin = CommunityAllowedOrigin(
        community_id=community.id,
        origin=origin,
    )
    session.add(allowed_origin)

    auth_provider = CommunityAuthProvider(
        community_id=community.id,
        issuer=issuer,
        algorithm="HS256",
        secret=secret,
    )
    session.add(auth_provider)

    await session.commit()

    return {
        "owner": owner,
        "community": community,
        "api_key": api_key,
        "allowed_origin": allowed_origin,
        "auth_provider": auth_provider,
        "public_key": public_key,
        "origin": origin,
        "issuer": issuer,
        "secret": secret,
    }
