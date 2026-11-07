import jwt
from datetime import datetime, timedelta, timezone


def embed_headers(
    *,
    public_key="tfspub_test",
    origin="https://example.com",
    token: str | None = None,
):
    headers = {
        "Origin": origin,
        "X-ThreadFS-Community-Key": public_key,
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def create_test_token(
    *,
    secret="test-secret",
    issuer="example-site",
    subject="user-1",
    username="Sora",
    avatar_url="https://example.com/avatar.png",
    expires_delta=timedelta(minutes=15),
    role: str | None = None,
    claims: dict | None = None,
    omit_avatar: bool = False,
):
    now = datetime.now(timezone.utc)

    extra = {"threadfs_role": role} if role else {}

    return jwt.encode(
        {
            **extra,
            **(claims or {}),
            "sub": subject,
            "username": username,
            **({} if omit_avatar else {"avatar_url": avatar_url}),
            "iss": issuer,
            "aud": "threadfs",
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
        },
        secret,
        algorithm="HS256",
    )
