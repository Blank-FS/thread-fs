# tests/integration/test_rate_limit.py

import os

import pytest
from fastapi import HTTPException

from app.core.rate_limit import RateLimiter, RateLimitRule

RULE = RateLimitRule(name="test", limit=3, window_seconds=60)


async def hits_allowed(limiter, key, count=6):
    allowed = 0
    for _ in range(count):
        try:
            await limiter.check(key=key, rule=RULE)
            allowed += 1
        except HTTPException as error:
            assert error.status_code == 429
            assert int(error.headers["Retry-After"]) >= 1
    return allowed


@pytest.mark.anyio
async def test_each_key_has_its_own_limit():
    limiter = RateLimiter(None)
    assert await hits_allowed(limiter, "a") == 3
    assert await hits_allowed(limiter, "b") == 3


@pytest.mark.anyio
async def test_without_redis_each_worker_counts_alone():
    assert await hits_allowed(RateLimiter(None), "a") == 3
    assert await hits_allowed(RateLimiter(None), "a") == 3


@pytest.mark.anyio
async def test_a_redis_that_cant_be_reached_doesnt_stop_requests():
    limiter = RateLimiter("redis://127.0.0.1:1/0")
    assert await hits_allowed(limiter, "a") == 3


@pytest.mark.anyio
@pytest.mark.skipif(not os.environ.get("TEST_REDIS_URL"), reason="Needs TEST_REDIS_URL")
async def test_workers_share_a_limit_through_redis():
    url = os.environ["TEST_REDIS_URL"]
    key = f"shared-{os.getpid()}"

    first, second = RateLimiter(url), RateLimiter(url)
    assert await hits_allowed(first, key, count=2) == 2
    assert await hits_allowed(second, key, count=4) == 1
    assert await hits_allowed(first, key, count=1) == 0
