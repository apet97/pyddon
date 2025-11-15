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
        self.last_request_time = 0.0

    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit.
        
        This ensures that requests are spaced out by at least min_interval seconds.
        """
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - time_since_last)

        self.last_request_time = asyncio.get_event_loop().time()
