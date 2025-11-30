"""Data retention and cleanup utilities."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Type

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase


async def cleanup_old_records(
    session: AsyncSession,
    model: Type[DeclarativeBase],
    timestamp_column: str,
    days: int,
    batch_size: int = 1000
) -> int:
    """Delete records older than specified days.
    
    Args:
        session: Database session
        model: SQLAlchemy model class
        timestamp_column: Name of the timestamp column to check
        days: Number of days to retain
        batch_size: Number of records to delete per batch
        
    Returns:
        Total number of records deleted
    """
    if days <= 0:
        return 0
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    column = getattr(model, timestamp_column)
    
    # Delete in batches to avoid locking the table for too long
    total_deleted = 0
    while True:
        stmt = delete(model).where(column < cutoff).limit(batch_size)
        result = await session.execute(stmt)
        await session.commit()
        
        deleted = result.rowcount
        total_deleted += deleted
        
        if deleted < batch_size:
            break
        
        # Small delay between batches
        await asyncio.sleep(0.1)
    
    return total_deleted


async def run_retention_cleanup(
    session: AsyncSession,
    cleanup_tasks: list[tuple[Type[DeclarativeBase], str, int]]
) -> dict:
    """Run retention cleanup for multiple models.
    
    Args:
        session: Database session
        cleanup_tasks: List of (model, timestamp_column, retention_days) tuples
        
    Returns:
        Dictionary with cleanup results per model
    """
    results = {}
    
    for model, timestamp_column, retention_days in cleanup_tasks:
        try:
            deleted = await cleanup_old_records(
                session, model, timestamp_column, retention_days
            )
            results[model.__tablename__] = {
                "status": "success",
                "deleted": deleted,
                "retention_days": retention_days
            }
        except Exception as e:
            results[model.__tablename__] = {
                "status": "error",
                "error": str(e),
                "retention_days": retention_days
            }
    
    return results
