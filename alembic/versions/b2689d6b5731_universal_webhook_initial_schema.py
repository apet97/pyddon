"""universal_webhook_initial_schema

Revision ID: b2689d6b5731
Revises: 5978bbfafc2d
Create Date: 2025-11-14 00:27:17.742490

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2689d6b5731'
down_revision: Union[str, None] = '5978bbfafc2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create universal_webhook_installation table
    op.create_table(
        'universal_webhook_installation',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('addon_id', sa.String(length=64), nullable=False),
        sa.Column('api_url', sa.String(length=255), nullable=False),
        sa.Column('addon_token', sa.String(length=255), nullable=False),
        sa.Column('settings_json', sa.JSON(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id')
    )
    op.create_index(op.f('ix_universal_webhook_installation_workspace_id'), 
                    'universal_webhook_installation', ['workspace_id'], unique=False)

    # Create universal_webhook_bootstrap_state table
    op.create_table(
        'universal_webhook_bootstrap_state',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id')
    )
    op.create_index(op.f('ix_universal_webhook_bootstrap_state_workspace_id'),
                    'universal_webhook_bootstrap_state', ['workspace_id'], unique=False)

    # Create universal_webhook_entity_cache table
    op.create_table(
        'universal_webhook_entity_cache',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('endpoint_id', sa.String(length=128), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_universal_webhook_entity_cache_workspace_id'),
                    'universal_webhook_entity_cache', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_universal_webhook_entity_cache_entity_type'),
                    'universal_webhook_entity_cache', ['entity_type'], unique=False)
    op.create_index(op.f('ix_universal_webhook_entity_cache_fetched_at'),
                    'universal_webhook_entity_cache', ['fetched_at'], unique=False)

    # Create universal_webhook_log table
    op.create_table(
        'universal_webhook_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('custom_source', sa.String(length=64), nullable=True),
        sa.Column('event_type', sa.String(length=128), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_universal_webhook_log_workspace_id'),
                    'universal_webhook_log', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_universal_webhook_log_source'),
                    'universal_webhook_log', ['source'], unique=False)
    op.create_index(op.f('ix_universal_webhook_log_custom_source'),
                    'universal_webhook_log', ['custom_source'], unique=False)
    op.create_index(op.f('ix_universal_webhook_log_event_type'),
                    'universal_webhook_log', ['event_type'], unique=False)
    op.create_index(op.f('ix_universal_webhook_log_received_at'),
                    'universal_webhook_log', ['received_at'], unique=False)

    # Create universal_webhook_flow table
    op.create_table(
        'universal_webhook_flow',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('trigger_source', sa.String(length=32), nullable=False),
        sa.Column('trigger_event_types', sa.JSON(), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_universal_webhook_flow_workspace_id'),
                    'universal_webhook_flow', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_universal_webhook_flow_enabled'),
                    'universal_webhook_flow', ['enabled'], unique=False)

    # Create universal_webhook_flow_execution table
    op.create_table(
        'universal_webhook_flow_execution',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('flow_id', sa.Integer(), nullable=False),
        sa.Column('webhook_log_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('actions_result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_universal_webhook_flow_execution_workspace_id'),
                    'universal_webhook_flow_execution', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_universal_webhook_flow_execution_flow_id'),
                    'universal_webhook_flow_execution', ['flow_id'], unique=False)
    op.create_index(op.f('ix_universal_webhook_flow_execution_webhook_log_id'),
                    'universal_webhook_flow_execution', ['webhook_log_id'], unique=False)
    op.create_index(op.f('ix_universal_webhook_flow_execution_status'),
                    'universal_webhook_flow_execution', ['status'], unique=False)
    op.create_index(op.f('ix_universal_webhook_flow_execution_created_at'),
                    'universal_webhook_flow_execution', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_universal_webhook_flow_execution_created_at'),
                  table_name='universal_webhook_flow_execution')
    op.drop_index(op.f('ix_universal_webhook_flow_execution_status'),
                  table_name='universal_webhook_flow_execution')
    op.drop_index(op.f('ix_universal_webhook_flow_execution_webhook_log_id'),
                  table_name='universal_webhook_flow_execution')
    op.drop_index(op.f('ix_universal_webhook_flow_execution_flow_id'),
                  table_name='universal_webhook_flow_execution')
    op.drop_index(op.f('ix_universal_webhook_flow_execution_workspace_id'),
                  table_name='universal_webhook_flow_execution')
    op.drop_table('universal_webhook_flow_execution')

    op.drop_index(op.f('ix_universal_webhook_flow_enabled'),
                  table_name='universal_webhook_flow')
    op.drop_index(op.f('ix_universal_webhook_flow_workspace_id'),
                  table_name='universal_webhook_flow')
    op.drop_table('universal_webhook_flow')

    op.drop_index(op.f('ix_universal_webhook_log_received_at'),
                  table_name='universal_webhook_log')
    op.drop_index(op.f('ix_universal_webhook_log_event_type'),
                  table_name='universal_webhook_log')
    op.drop_index(op.f('ix_universal_webhook_log_custom_source'),
                  table_name='universal_webhook_log')
    op.drop_index(op.f('ix_universal_webhook_log_source'),
                  table_name='universal_webhook_log')
    op.drop_index(op.f('ix_universal_webhook_log_workspace_id'),
                  table_name='universal_webhook_log')
    op.drop_table('universal_webhook_log')

    op.drop_index(op.f('ix_universal_webhook_entity_cache_fetched_at'),
                  table_name='universal_webhook_entity_cache')
    op.drop_index(op.f('ix_universal_webhook_entity_cache_entity_type'),
                  table_name='universal_webhook_entity_cache')
    op.drop_index(op.f('ix_universal_webhook_entity_cache_workspace_id'),
                  table_name='universal_webhook_entity_cache')
    op.drop_table('universal_webhook_entity_cache')

    op.drop_index(op.f('ix_universal_webhook_bootstrap_state_workspace_id'),
                  table_name='universal_webhook_bootstrap_state')
    op.drop_table('universal_webhook_bootstrap_state')

    op.drop_index(op.f('ix_universal_webhook_installation_workspace_id'),
                  table_name='universal_webhook_installation')
    op.drop_table('universal_webhook_installation')
