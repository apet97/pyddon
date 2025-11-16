"""Rate limiter for Clockify API requests."""
from __future__ import annotations

import asyncio


class RateLimiter:
    """Simple rate limiter to enforce max requests per second.
    
    Respects Clockify's 50 RPS per workspace rate limit by throttling requests.
    """

    def __init__(self, max_rps: int):
        """Initialize rate limiter.
        
        Args:
            max_rps: Maximum requests per second
        """
        self.max_rps = max_rps
        self.min_interval = 1.0 / max_rps
        self._next_allowed_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit.
        
        This ensures that requests are spaced out by at least min_interval seconds.
        """
        loop = asyncio.get_running_loop()
        while True:
            async with self._lock:
                now = loop.time()
                if now >= self._next_allowed_time:
                    self._next_allowed_time = now + self.min_interval
                    return
                wait_time = self._next_allowed_time - now
            await asyncio.sleep(wait_time)
