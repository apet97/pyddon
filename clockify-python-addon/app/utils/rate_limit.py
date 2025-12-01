from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Optional

from app.config import get_settings
from app.metrics import metrics_registry
from app.utils.errors import RateLimitError
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RateLimiter:
    """In-memory token bucket rate limiter with workspace isolation."""
    
    def __init__(self, rps: int = 50):
        self.rps = max(1, rps)
        self._buckets: dict[str, dict[str, Optional[float]]] = defaultdict(
            self._create_bucket
        )
        self._lock = asyncio.Lock()
    
    def _create_bucket(self) -> dict[str, Optional[float]]:
        """Create a new workspace bucket with a full token balance."""
        return {"tokens": float(self.rps), "last_update": None}
    
    async def acquire(self, workspace_id: str) -> None:
        """Acquire a token for the given workspace, blocking if necessary."""
        if not settings.rate_limit_enabled:
            return
        
        while True:
            async with self._lock:
                bucket = self._buckets[workspace_id]
                self._refill(bucket)
                
                if bucket["tokens"] >= 1:
                    bucket["tokens"] -= 1
                    return
                
                wait_time = (1 - bucket["tokens"]) / self.rps
                wait_time = max(wait_time, 0.0)
            
            if wait_time <= 0:
                # Re-check immediately if timing drift made the wait negative/zero
                continue
            
            logger.warning(
                "rate_limit_wait",
                workspace_id=workspace_id,
                wait_time=wait_time
            )
            metrics_registry.record_rate_limit_wait(wait_time)
            await asyncio.sleep(wait_time)
    
    async def check_limit(self, workspace_id: str, raise_error: bool = True) -> bool:
        """Check if request is within rate limit without consuming token."""
        if not settings.rate_limit_enabled:
            return True
        
        async with self._lock:
            bucket = self._buckets[workspace_id]
            self._refill(bucket)
            current_tokens = bucket["tokens"]
            
            if current_tokens < 1:
                if raise_error:
                    raise RateLimitError(
                        f"Rate limit exceeded for workspace {workspace_id}",
                        details={"workspace_id": workspace_id, "limit_rps": self.rps}
                    )
                return False
            
            return True

    def _refill(self, bucket: dict[str, Optional[float]]) -> None:
        """Replenish tokens in a bucket based on elapsed time."""
        loop_time = asyncio.get_running_loop().time()
        last_update = bucket["last_update"]
        if last_update is None:
            bucket["last_update"] = loop_time
            return
        time_passed = loop_time - last_update
        if time_passed <= 0:
            return
        bucket["tokens"] = min(self.rps, bucket["tokens"] + time_passed * self.rps)
        bucket["last_update"] = loop_time


_REDIS_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local now = tonumber(ARGV[2])

local tokens = tonumber(redis.call("HGET", key, "tokens"))
local last = tonumber(redis.call("HGET", key, "ts"))

if tokens == nil or last == nil then
  tokens = rate
  last = now
end

local elapsed = now - last
if elapsed > 0 then
  tokens = math.min(rate, tokens + elapsed * rate)
  last = now
end

if tokens < 1 then
  redis.call("HSET", key, "tokens", tokens, "ts", last)
  redis.call("EXPIRE", key, 120)
  local wait_time = (1 - tokens) / rate
  return {0, wait_time}
end

tokens = tokens - 1
redis.call("HSET", key, "tokens", tokens, "ts", now)
redis.call("EXPIRE", key, 120)
return {1, 0}
"""


_REDIS_CHECK_SCRIPT = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local now = tonumber(ARGV[2])

local tokens = tonumber(redis.call("HGET", key, "tokens"))
local last = tonumber(redis.call("HGET", key, "ts"))

if tokens == nil or last == nil then
  tokens = rate
  last = now
end

local elapsed = now - last
if elapsed > 0 then
  tokens = math.min(rate, tokens + elapsed * rate)
  last = now
end

redis.call("HSET", key, "tokens", tokens, "ts", now)
redis.call("EXPIRE", key, 120)

if tokens < 1 then
  local wait_time = (1 - tokens) / rate
  return {0, wait_time}
end

return {1, 0}
"""


class RedisRateLimiter:
    """Distributed token bucket using Redis for workspace isolation."""

    def __init__(self, rps: int, redis_url: str):
        self.rps = max(1, rps)
        self.redis_url = redis_url
        self._redis = None
        self._fallback = RateLimiter(rps=self.rps)

    async def _get_client(self):
        if self._redis:
            return self._redis
        try:
            import redis.asyncio as redis
        except Exception as exc:  # pragma: no cover - import guard
            logger.error("redis_import_failed", error=str(exc))
            return None

        try:
            self._redis = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=False)
            return self._redis
        except Exception as exc:
            logger.error("redis_connection_failed", error=str(exc))
            return None

    def _key(self, workspace_id: str) -> str:
        return f"clockify:addon:ratelimit:{workspace_id}"

    async def acquire(self, workspace_id: str) -> None:
        if not settings.rate_limit_enabled:
            return

        client = await self._get_client()
        if client is None:
            # Fallback to in-memory limiter on redis issues
            return await self._fallback.acquire(workspace_id)

        while True:
            try:
                allowed, wait_time = await client.eval(
                    _REDIS_ACQUIRE_SCRIPT,
                    keys=[self._key(workspace_id)],
                    args=[self.rps, time.time()],
                )
                allowed = int(allowed)
                wait_time = float(wait_time)
            except Exception as exc:
                logger.error("redis_rate_limit_error", error=str(exc))
                return await self._fallback.acquire(workspace_id)

            if allowed == 1:
                return

            wait_time = max(wait_time, 0.0)
            logger.warning(
                "rate_limit_wait",
                workspace_id=workspace_id,
                wait_time=wait_time
            )
            metrics_registry.record_rate_limit_wait(wait_time)
            await asyncio.sleep(wait_time)

    async def check_limit(self, workspace_id: str, raise_error: bool = True) -> bool:
        if not settings.rate_limit_enabled:
            return True

        client = await self._get_client()
        if client is None:
            return await self._fallback.check_limit(workspace_id, raise_error=raise_error)

        try:
            allowed, wait_time = await client.eval(
                _REDIS_CHECK_SCRIPT,
                keys=[self._key(workspace_id)],
                args=[self.rps, time.time()],
            )
            allowed = int(allowed)
            wait_time = float(wait_time)
        except Exception as exc:
            logger.error("redis_rate_limit_error", error=str(exc))
            return await self._fallback.check_limit(workspace_id, raise_error=raise_error)

        if allowed == 1:
            return True

        if raise_error:
            raise RateLimitError(
                f"Rate limit exceeded for workspace {workspace_id}",
                details={"workspace_id": workspace_id, "limit_rps": self.rps, "wait_time": wait_time},
            )
        return False


# Global rate limiter instance
if settings.use_redis:
    rate_limiter = RedisRateLimiter(rps=settings.rate_limit_rps, redis_url=settings.redis_url)
else:
    rate_limiter = RateLimiter(rps=settings.rate_limit_rps)


async def rate_limit_request(workspace_id: str) -> None:
    """Rate limit a request for the given workspace."""
    await rate_limiter.acquire(workspace_id)
