# app/core/rate_limit.py

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Counts a hit and starts the window on the first one, in one step so workers can't interleave
COUNT_HIT = """
local hits = redis.call('INCR', KEYS[1])
if hits == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {hits, redis.call('TTL', KEYS[1])}
"""


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int


class InMemoryCounter:
    """Counts within one process: for development, and when Redis can't be reached."""

    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    async def hit(self, bucket: str, rule: RateLimitRule) -> int | None:
        now = time.monotonic()
        window_start = now - rule.window_seconds
        hits = self._hits[bucket]

        while hits and hits[0] <= window_start:
            hits.popleft()

        if len(hits) >= rule.limit:
            return max(1, int(rule.window_seconds - (now - hits[0])))

        hits.append(now)
        return None


class RedisCounter:
    """Counts across every worker. A slow Redis has to fail fast: this runs on every request."""

    def __init__(self, url: str) -> None:
        self._redis = Redis.from_url(url, socket_timeout=0.25, socket_connect_timeout=0.25)
        self._count_hit = self._redis.register_script(COUNT_HIT)

    async def hit(self, bucket: str, rule: RateLimitRule) -> int | None:
        hits, ttl = await self._count_hit(keys=[f"rate:{bucket}"], args=[rule.window_seconds])
        return max(1, int(ttl)) if hits > rule.limit else None


class RateLimiter:
    def __init__(self, redis_url: str | None) -> None:
        self._shared = RedisCounter(redis_url) if redis_url else None
        self._local = InMemoryCounter()

    async def check(self, *, key: str, rule: RateLimitRule) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        bucket = f"{rule.name}:{key}"
        try:
            retry_after = await (self._shared or self._local).hit(bucket, rule)
        except (RedisError, OSError) as error:
            # Comments keep working without Redis, on each worker's own count
            logger.warning("Rate limiting without Redis: %s", error)
            retry_after = await self._local.hit(bucket, rule)

        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )


rate_limiter = RateLimiter(settings.REDIS_URL)


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


async def check_ip_rate_limit(
    request: Request,
    *,
    name: str,
    limit: int,
    window_seconds: int,
) -> None:
    key = make_ip_rate_limit_key(request)

    await rate_limiter.check(
        key=key,
        rule=RateLimitRule(
            name=name,
            limit=limit,
            window_seconds=window_seconds,
        ),
    )


async def check_user_rate_limit(
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

    await rate_limiter.check(
        key=key,
        rule=RateLimitRule(
            name=name,
            limit=limit,
            window_seconds=window_seconds,
        ),
    )
