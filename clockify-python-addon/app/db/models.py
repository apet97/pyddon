from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, JSON, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Installation(Base):
    """Represents an installed addon instance in a workspace."""
    
    __tablename__ = "installations"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False, index=True)
    addon_id = Column(String, nullable=False)
    addon_token = Column(Text, nullable=False)
    api_url = Column(String, nullable=False)
    status = Column(String, default="ACTIVE")
    settings = Column(JSON, default=dict)
    webhook_ids = Column(JSON, default=list)  # Store registered webhook IDs for cleanup
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('ix_installations_workspace_active', workspace_id, status),
    )


class WebhookEvent(Base):
    """Stores received webhook events."""
    
    __tablename__ = "webhook_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True, nullable=False, index=True)
    workspace_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    event_metadata = Column(JSON, default=dict)
    received_at = Column(DateTime, default=func.now())
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('ix_webhooks_workspace_type', workspace_id, event_type),
        Index('ix_webhooks_processed', processed, received_at),
    )


class APICall(Base):
    """Logs API calls made through the no-code caller."""
    
    __tablename__ = "api_calls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    method = Column(String, nullable=False)
    request_params = Column(JSON, default=dict)
    request_body = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)
    response_body = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    developer_mode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    duration_ms = Column(Integer, nullable=True)
    
    __table_args__ = (
        Index('ix_api_calls_workspace_created', workspace_id, created_at),
    )


class BootstrapJob(Base):
    """Tracks bootstrap job execution."""
    
    __tablename__ = "bootstrap_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(String, nullable=False, index=True)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    total_endpoints = Column(Integer, default=0)
    completed_endpoints = Column(Integer, default=0)
    failed_endpoints = Column(Integer, default=0)
    errors = Column(JSON, default=list)
    results = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('ix_bootstrap_workspace_status', workspace_id, status),
    )


class WorkspaceData(Base):
    """Stores fetched workspace data from bootstrap."""
    
    __tablename__ = "workspace_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(String, nullable=True)
    data = Column(JSON, nullable=False)
    source_endpoint = Column(String, nullable=False)
    fetched_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('ix_workspace_data_entity', workspace_id, entity_type),
    )
