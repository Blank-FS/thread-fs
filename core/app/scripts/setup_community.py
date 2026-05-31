# app/scripts/setup_community.py

import argparse
import asyncio
import secrets
import uuid
import re
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.community import Community
from app.models.community_api_key import CommunityApiKey
from app.models.community_allowed_origin import CommunityAllowedOrigin
from app.models.community_auth_provider import CommunityAuthProvider
from app.models.user import User


def slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")

    if not slug:
        raise ValueError("Community slug cannot be empty")

    return slug


def generate_public_key() -> str:
    return f"tfspub_{secrets.token_urlsafe(24)}"


def generate_secret_hash() -> str:
    return f"tfshash_{secrets.token_urlsafe(24)}"


def generate_auth_secret() -> str:
    return f"tfssec_{secrets.token_urlsafe(48)}"


@dataclass
class SetupResult:
    community: Community
    api_key: CommunityApiKey
    auth_provider: CommunityAuthProvider
    created_auth_secret: str | None


async def get_or_create_admin_user(
    session: AsyncSession,
    *,
    email: str,
) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        return user

    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="setup-script-user-no-password-login",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )

    session.add(user)
    await session.flush()

    return user


async def get_or_create_community(
    session: AsyncSession,
    *,
    owner_user_id,
    name: str,
    slug: str,
    description: str | None,
    allow_anonymous_read: bool,
) -> Community:
    result = await session.execute(select(Community).where(Community.slug == slug))
    community = result.scalar_one_or_none()

    if community:
        community.user_id = owner_user_id
        community.name = name
        community.description = description
        community.allow_anonymous_read = allow_anonymous_read
        await session.flush()
        return community

    community = Community(
        user_id=owner_user_id,
        name=name,
        slug=slug,
        description=description,
        allow_anonymous_read=allow_anonymous_read,
        thread_count=0,
    )

    session.add(community)
    await session.flush()

    return community


async def get_or_create_public_key(
    session: AsyncSession,
    *,
    community_id,
    public_key: str | None,
) -> CommunityApiKey:
    result = await session.execute(
        select(CommunityApiKey).where(
            CommunityApiKey.community_id == community_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key:
        return api_key

    api_key = CommunityApiKey(
        community_id=community_id,
        public_key=public_key or generate_public_key(),
        secret_hash=generate_secret_hash(),
    )

    session.add(api_key)
    await session.flush()

    return api_key


async def upsert_allowed_origins(
    session: AsyncSession,
    *,
    community_id,
    origins: list[str],
) -> list[CommunityAllowedOrigin]:
    created_or_existing: list[CommunityAllowedOrigin] = []

    for origin in origins:
        normalized = origin.rstrip("/")

        result = await session.execute(
            select(CommunityAllowedOrigin).where(
                CommunityAllowedOrigin.community_id == community_id,
                CommunityAllowedOrigin.origin == normalized,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            created_or_existing.append(existing)
            continue

        allowed_origin = CommunityAllowedOrigin(
            community_id=community_id,
            origin=normalized,
        )

        session.add(allowed_origin)
        await session.flush()

        created_or_existing.append(allowed_origin)

    return created_or_existing


async def get_or_create_auth_provider(
    session: AsyncSession,
    *,
    community_id,
    issuer: str,
    secret: str | None,
) -> tuple[CommunityAuthProvider, str]:
    result = await session.execute(
        select(CommunityAuthProvider).where(
            CommunityAuthProvider.community_id == community_id,
            CommunityAuthProvider.issuer == issuer,
        )
    )
    provider = result.scalar_one_or_none()

    if provider:
        return provider, provider.secret

    created_secret = secret or generate_auth_secret()

    provider = CommunityAuthProvider(
        community_id=community_id,
        issuer=issuer,
        algorithm="HS256",
        secret=created_secret,
    )

    session.add(provider)
    await session.flush()

    return provider, created_secret


async def setup_community(
    *,
    owner_email: str,
    name: str,
    slug: str | None,
    description: str | None,
    origins: list[str],
    issuer: str,
    public_key: str | None,
    auth_secret: str | None,
    allow_anonymous_read: bool,
) -> SetupResult:
    community_slug = slugify(slug or name)

    async with async_session_maker() as session:
        async with session.begin():
            owner_user = await get_or_create_admin_user(
                session,
                email=owner_email,
            )

            community = await get_or_create_community(
                session,
                owner_user_id=owner_user.id,
                name=name,
                slug=community_slug,
                description=description,
                allow_anonymous_read=allow_anonymous_read,
            )

            api_key = await get_or_create_public_key(
                session,
                community_id=community.id,
                public_key=public_key,
            )

            await upsert_allowed_origins(
                session,
                community_id=community.id,
                origins=origins,
            )

            auth_provider, created_auth_secret = await get_or_create_auth_provider(
                session,
                community_id=community.id,
                issuer=issuer,
                secret=auth_secret,
            )

        return SetupResult(
            community=community,
            api_key=api_key,
            auth_provider=auth_provider,
            created_auth_secret=created_auth_secret,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or update a ThreadFS community integration."
    )

    parser.add_argument("--name", required=True)
    parser.add_argument("--description", default=None)
    parser.add_argument(
        "--slug",
        default=None,
        help="Unique community slug. Defaults to slugified community name.",
    )
    parser.add_argument("--origin", action="append", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument(
        "--owner-email",
        required=True,
        help="Email for the ThreadFS admin/owner user.",
    )

    parser.add_argument("--public-key", default=None)
    parser.add_argument("--auth-secret", default=None)

    parser.add_argument(
        "--private-read",
        action="store_true",
        help="Disable anonymous comment reads.",
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    result = await setup_community(
        owner_email=args.owner_email,
        name=args.name,
        slug=args.slug,
        description=args.description,
        origins=args.origin,
        issuer=args.issuer,
        public_key=args.public_key,
        auth_secret=args.auth_secret,
        allow_anonymous_read=not args.private_read,
    )

    print("\nThreadFS community is ready.\n")
    print(f"Owner email:        {args.owner_email}")
    print(f"Community ID:       {result.community.id}")
    print(f"Community name:     {result.community.name}")
    print(f"Community slug:     {result.community.slug}")
    print(f"Community key:      {result.api_key.public_key}")
    print(f"Auth issuer:        {result.auth_provider.issuer}")
    print(f"Auth algorithm:     {result.auth_provider.algorithm}")

    if result.created_auth_secret:
        print("\nStore this secret in the host website backend only:")
        print(f"THREADFS_SECRET={result.created_auth_secret}")
    else:
        print("\nAuth provider already existed; existing secret was not printed.")

    print("\nAllowed origins:")
    for origin in args.origin:
        print(f"  - {origin.rstrip('/')}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
