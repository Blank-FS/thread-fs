# app/core/rate_limit.py

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from fastapi import HTTPException, Request, status

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def check(self, *, key: str, rule: RateLimitRule) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        now = time.monotonic()
        window_start = now - rule.window_seconds

        bucket_key = f"{rule.name}:{key}"
        hits = self._hits[bucket_key]

        while hits and hits[0] <= window_start:
            hits.popleft()

        if len(hits) >= rule.limit:
            retry_after = max(1, int(rule.window_seconds - (now - hits[0])))

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)


rate_limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    # If behind Cloudflare, prefer CF-Connecting-IP.
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    # If behind a trusted proxy/load balancer, X-Forwarded-For may be useful.
    # Only trust this if your reverse proxy strips untrusted incoming headers.
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def make_ip_rate_limit_key(request: Request) -> str:
    return f"ip:{get_client_ip(request)}"


def make_user_rate_limit_key(*, community_id: str, community_user_id: str) -> str:
    return f"community:{community_id}:user:{community_user_id}"


def check_ip_rate_limit(
    request: Request,
    *,
    name: str,
    limit: int,
    window_seconds: int,
) -> None:
    key = make_ip_rate_limit_key(request)

    rate_limiter.check(
        key=key,
        rule=RateLimitRule(
            name=name,
            limit=limit,
            window_seconds=window_seconds,
        ),
    )


def check_user_rate_limit(
    *,
    community_id: str,
    community_user_id: str,
    name: str,
    limit: int,
    window_seconds: int,
) -> None:
    key = make_user_rate_limit_key(
        community_id=community_id,
        community_user_id=community_user_id,
    )

    rate_limiter.check(
        key=key,
        rule=RateLimitRule(
            name=name,
            limit=limit,
            window_seconds=window_seconds,
        ),
    )
