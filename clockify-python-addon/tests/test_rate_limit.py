import asyncio
import time

import pytest

from app.utils.rate_limit import RateLimiter
from app.utils.errors import RateLimitError


@pytest.mark.asyncio
async def test_rate_limiter_enforces_wait_time():
    limiter = RateLimiter(rps=5)
    start = time.perf_counter()
    for _ in range(6):
        await limiter.acquire("workspace-1")
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.15
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_rate_limiter_check_limit_flags_exhausted_bucket():
    limiter = RateLimiter(rps=1)
    await limiter.acquire("workspace-2")
    available = await limiter.check_limit("workspace-2", raise_error=False)
    assert available is False
    with pytest.raises(RateLimitError):
        await limiter.check_limit("workspace-2", raise_error=True)


@pytest.mark.asyncio
async def test_rate_limiter_serializes_concurrent_requests():
    limiter = RateLimiter(rps=2)

    async def _consume():
        await limiter.acquire("workspace-3")

    start = time.perf_counter()
    await asyncio.gather(*(_consume() for _ in range(3)))
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.5
