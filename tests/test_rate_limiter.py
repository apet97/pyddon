import asyncio
import time

import pytest

from clockify_core.rate_limiter import RateLimiter
from clockify_core.metrics import get_metrics_collector


@pytest.mark.asyncio
async def test_rate_limiter_enforces_min_interval():
    limiter = RateLimiter(max_rps=5)  # 200ms spacing
    start = time.perf_counter()
    for _ in range(5):
        await limiter.acquire()
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.8  # four enforced waits
    assert elapsed < 1.5


@pytest.mark.asyncio
async def test_rate_limiter_fast_path_when_rps_high():
    limiter = RateLimiter(max_rps=1000)
    start = time.perf_counter()
    for _ in range(20):
        await limiter.acquire()
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05


@pytest.mark.asyncio
async def test_rate_limiter_serializes_concurrent_calls():
    limiter = RateLimiter(max_rps=2)  # 500ms spacing

    async def make_call():
        await limiter.acquire()

    start = time.perf_counter()
    await asyncio.gather(*(make_call() for _ in range(3)))
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.5  # at least one wait enforced


@pytest.mark.asyncio
async def test_rate_limiter_records_wait_metric():
    collector = get_metrics_collector()
    before = collector.get_metrics()["counters"].get("rate_limiter.waits", 0)
    limiter = RateLimiter(max_rps=1)
    await limiter.acquire()
    await limiter.acquire()  # should trigger a wait
    after = collector.get_metrics()["counters"].get("rate_limiter.waits", 0)
    assert after >= before + 1
