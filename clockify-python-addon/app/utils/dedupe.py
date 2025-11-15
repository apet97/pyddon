import asyncio
import time
from typing import Set, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DeduplicationStore:
    """
    Database-backed deduplication store with memory cache.
    
    Uses the WebhookEvent table's unique constraint on event_id
    to ensure duplicates are rejected even across restarts.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        # Memory cache for fast duplicate checks
        self._memory_cache: dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def is_duplicate(self, event_id: str, db_session=None) -> bool:
        """
        Check if event has been processed recently.
        
        First checks memory cache for speed, then DB for persistence.
        """
        async with self._lock:
            # Check memory cache first
            await self._cleanup_memory_cache()
            
            if event_id in self._memory_cache:
                logger.info("duplicate_event_detected_memory", event_id=event_id)
                return True
            
            # Check DB if session provided
            if db_session:
                try:
                    from app.db.models import WebhookEvent
                    result = await db_session.execute(
                        select(WebhookEvent).where(WebhookEvent.event_id == event_id)
                    )
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        logger.info("duplicate_event_detected_db", event_id=event_id)
                        # Add to memory cache
                        self._memory_cache[event_id] = time.time()
                        return True
                        
                except Exception as e:
                    logger.error("dedupe_db_check_failed", event_id=event_id, error=str(e))
                    # Fall through to mark as not duplicate (fail open for DB errors)
            
            # Mark as seen in memory cache
            self._memory_cache[event_id] = time.time()
            return False
    
    async def _cleanup_memory_cache(self) -> None:
        """Remove expired entries from memory cache."""
        now = time.time()
        expired = [
            event_id for event_id, timestamp in self._memory_cache.items()
            if now - timestamp > self.ttl_seconds
        ]
        for event_id in expired:
            del self._memory_cache[event_id]
        
        if expired:
            logger.debug("dedupe_memory_cleanup", removed_count=len(expired))


# Global deduplication store
dedupe_store = DeduplicationStore(ttl_seconds=3600)


async def is_duplicate_event(event_id: str, db_session=None) -> bool:
    """
    Check if an event is a duplicate.
    
    Args:
        event_id: Unique event identifier
        db_session: Optional database session for persistent check
    
    Returns:
        True if duplicate, False otherwise
    """
    return await dedupe_store.is_duplicate(event_id, db_session)
