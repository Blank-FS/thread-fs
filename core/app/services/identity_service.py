# app/services/identity_service.py

from uuid import UUID
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.repositories import community_auth_provider as auth_provider_repo
from app.repositories import community_user as community_user_repo


class VerifiedIdentity:
    def __init__(
        self,
        *,
        identity_provider: str,
        external_user_id: str,
        display_name: str | None,
        avatar_url: str | None,
        threadfs_user_id: UUID | None = None,
    ):
        self.identity_provider = identity_provider
        self.external_user_id = external_user_id
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.threadfs_user_id = threadfs_user_id


def _unverified_issuer(token: str) -> str:
    try:
        claims = jwt.get_unverified_claims(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth token",
        )

    issuer = claims.get("iss")
    if not issuer or not isinstance(issuer, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth token missing issuer",
        )

    return issuer


async def verify_external_identity_token(
    session: AsyncSession,
    *,
    community: Community,
    token: str,
) -> VerifiedIdentity:
    issuer = _unverified_issuer(token)

    provider = await auth_provider_repo.get_auth_provider_by_issuer(
        session,
        community_id=community.id,
        issuer=issuer,
    )

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown auth issuer for this community",
        )

    if provider.algorithm != "HS256":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Only HS256 auth providers are supported for now",
        )

    if not provider.secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth provider is missing secret",
        )

    try:
        claims = jwt.decode(
            token,
            provider.secret,
            algorithms=[provider.algorithm],
            audience=provider.audience,
            issuer=provider.issuer,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth token",
        )

    subject = claims.get("sub")
    if not subject or not isinstance(subject, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth token missing subject",
        )

    token_type = claims.get("typ")
    if token_type and token_type != "threadfs_external_user":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    display_name = claims.get("name") or claims.get("username")
    avatar_url = claims.get("avatar_url")

    if display_name is not None and not isinstance(display_name, str):
        display_name = None

    if avatar_url is not None and not isinstance(avatar_url, str):
        avatar_url = None

    return VerifiedIdentity(
        identity_provider="external",
        external_user_id=subject,
        display_name=display_name,
        avatar_url=avatar_url,
    )


async def get_or_create_community_user_for_identity(
    session: AsyncSession,
    *,
    community: Community,
    identity: VerifiedIdentity,
):
    existing = await community_user_repo.get_community_user_by_identity(
        session,
        community_id=community.id,
        identity_provider=identity.identity_provider,
        external_user_id=identity.external_user_id,
    )

    if existing:
        changed = False

        if identity.display_name and existing.display_name != identity.display_name:
            existing.display_name = identity.display_name
            changed = True

        if identity.avatar_url and existing.avatar_url != identity.avatar_url:
            existing.avatar_url = identity.avatar_url
            changed = True

        if (
            identity.threadfs_user_id
            and existing.threadfs_user_id != identity.threadfs_user_id
        ):
            existing.threadfs_user_id = identity.threadfs_user_id
            changed = True

        if changed:
            await session.commit()
            await session.refresh(existing)

        return existing

    community_user = await community_user_repo.create_community_user(
        session,
        community_id=community.id,
        identity_provider=identity.identity_provider,
        external_user_id=identity.external_user_id,
        display_name=identity.display_name,
        avatar_url=identity.avatar_url,
        threadfs_user_id=identity.threadfs_user_id,
    )

    await session.commit()
    return community_user
