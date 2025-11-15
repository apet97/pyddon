from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Installation(Base):
    __tablename__ = "api_studio_installation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    addon_id: Mapped[str] = mapped_column(String(64))
    api_url: Mapped[str] = mapped_column(String(255))
    addon_token: Mapped[str] = mapped_column(String(255))
    settings_json: Mapped[Optional[dict[str, Any]]] = mapped_column(SQLiteJSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )


class BootstrapState(Base):
    __tablename__ = "api_studio_bootstrap_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )


class EntityCache(Base):
    __tablename__ = "api_studio_entity_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    endpoint_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WebhookLog(Base):
    __tablename__ = "api_studio_webhook_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128))
    headers: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON)
    payload: Mapped[dict[str, Any]] = mapped_column(SQLiteJSON)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Flow(Base):
    __tablename__ = "api_studio_flow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger_event_types: Mapped[list[str]] = mapped_column(SQLiteJSON)
    conditions: Mapped[Optional[dict[str, Any]]] = mapped_column(SQLiteJSON, nullable=True)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(SQLiteJSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )


class FlowExecution(Base):
    __tablename__ = "api_studio_flow_execution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    flow_id: Mapped[int] = mapped_column(Integer, index=True)
    webhook_log_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(32))
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actions_result: Mapped[Optional[dict[str, Any]]] = mapped_column(SQLiteJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
