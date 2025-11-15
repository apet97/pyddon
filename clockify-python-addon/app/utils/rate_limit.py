import asyncio
import time
from typing import Optional
from collections import defaultdict
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.errors import RateLimitError

settings = get_settings()
logger = get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter with workspace isolation."""
    
    def __init__(self, rps: int = 50):
        self.rps = max(1, rps)
        self._buckets: dict = defaultdict(
            lambda: {"tokens": float(self.rps), "last_update": time.time()}
        )
        self._lock = asyncio.Lock()
    
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
                wait_time = max(wait_time, 0)
            
            logger.warning(
                "rate_limit_wait",
                workspace_id=workspace_id,
                wait_time=wait_time
            )
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

    def _refill(self, bucket: dict) -> None:
        """Replenish tokens in a bucket based on elapsed time."""
        now = time.time()
        time_passed = now - bucket["last_update"]
        if time_passed <= 0:
            return
        bucket["tokens"] = min(self.rps, bucket["tokens"] + time_passed * self.rps)
        bucket["last_update"] = now


# Global rate limiter instance
rate_limiter = RateLimiter(rps=settings.rate_limit_rps)


async def rate_limit_request(workspace_id: str) -> None:
    """Rate limit a request for the given workspace."""
    await rate_limiter.acquire(workspace_id)
