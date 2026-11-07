# app/services/identity_service.py

from dataclasses import dataclass
from uuid import UUID
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community
from app.repositories import community_auth_provider as auth_provider_repo
from app.repositories import community_user as community_user_repo


@dataclass(frozen=True)
class ThreadClaim:
    """What the host's server says about a thread, signed into the token."""

    id: str
    title: str | None
    url: str | None


class VerifiedIdentity:
    def __init__(
        self,
        *,
        identity_provider: str,
        external_user_id: str,
        display_name: str | None,
        avatar_url: str | None,
        updates_avatar: bool = False,
        avatar_frame_url: str | None = None,
        updates_avatar_frame: bool = False,
        threadfs_user_id: UUID | None = None,
        staff_role: str | None = None,
        signed_threads: bool = False,
        thread_claim: ThreadClaim | None = None,
    ):
        self.identity_provider = identity_provider
        self.external_user_id = external_user_id
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.updates_avatar = updates_avatar
        self.avatar_frame_url = avatar_frame_url
        self.updates_avatar_frame = updates_avatar_frame
        self.threadfs_user_id = threadfs_user_id
        self.staff_role = staff_role
        self.signed_threads = signed_threads
        self.thread_claim = thread_claim


# The host site decides who its staff are: it signs this claim into the token, so nobody can give it to themselves
# without the community's auth secret, and no ThreadFS account is needed.
STAFF_ROLE_CLAIM = "threadfs_role"
STAFF_ROLES = {"moderator", "admin"}

# A thread's title and link come from whoever posts, unless the host vouches for them. A host that sets
# SIGNED_THREADS_CLAIM says its server decides: browser-sent details are ignored, and only a thread named in
# THREAD_CLAIM can be created. The host can't be impersonated here, for the same reason as the staff role.
SIGNED_THREADS_CLAIM = "threadfs_signed_threads"
THREAD_CLAIM = "threadfs_thread"


def _thread_claim(claims: dict) -> ThreadClaim | None:
    value = claims.get(THREAD_CLAIM)
    if not isinstance(value, dict) or not isinstance(value.get("id"), str):
        return None

    title, url = value.get("title"), value.get("url")
    return ThreadClaim(
        id=value["id"],
        title=title[:512] if isinstance(title, str) else None,
        url=url[:2048] if isinstance(url, str) else None,
    )


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
    # A null avatar means the user has none, so it clears the stored one. A token without the claim says nothing about it
    updates_avatar = "avatar_url" in claims and (avatar_url is None or isinstance(avatar_url, str))
    # The same for the frame drawn over it
    avatar_frame_url = claims.get("avatar_frame_url")
    updates_avatar_frame = "avatar_frame_url" in claims and (
        avatar_frame_url is None or isinstance(avatar_frame_url, str)
    )

    if display_name is not None and not isinstance(display_name, str):
        display_name = None

    if avatar_url is not None and not isinstance(avatar_url, str):
        avatar_url = None

    return VerifiedIdentity(
        identity_provider="external",
        external_user_id=subject,
        display_name=display_name,
        avatar_url=avatar_url,
        updates_avatar=updates_avatar,
        avatar_frame_url=avatar_frame_url if isinstance(avatar_frame_url, str) else None,
        updates_avatar_frame=updates_avatar_frame,
        staff_role=claims.get(STAFF_ROLE_CLAIM)
        if claims.get(STAFF_ROLE_CLAIM) in STAFF_ROLES
        else None,
        signed_threads=claims.get(SIGNED_THREADS_CLAIM) is True,
        thread_claim=_thread_claim(claims),
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

        if identity.updates_avatar and existing.avatar_url != identity.avatar_url:
            existing.avatar_url = identity.avatar_url
            changed = True

        if identity.updates_avatar_frame and existing.avatar_frame_url != identity.avatar_frame_url:
            existing.avatar_frame_url = identity.avatar_frame_url
            changed = True

        if existing.last_staff_role != identity.staff_role:
            existing.last_staff_role = identity.staff_role
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
        avatar_frame_url=identity.avatar_frame_url,
        last_staff_role=identity.staff_role,
        threadfs_user_id=identity.threadfs_user_id,
    )

    await session.commit()
    return community_user
