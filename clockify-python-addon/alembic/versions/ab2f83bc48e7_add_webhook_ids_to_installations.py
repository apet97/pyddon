"""add_webhook_ids_to_installations

Revision ID: ab2f83bc48e7
Revises: 
Create Date: 2025-11-14 02:51:20.736442

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab2f83bc48e7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add webhook_ids column to installations table
    op.add_column('installations', sa.Column('webhook_ids', sa.JSON(), nullable=True))
    # Set default empty list for existing rows
    op.execute("UPDATE installations SET webhook_ids = '[]' WHERE webhook_ids IS NULL")


def downgrade() -> None:
    # Remove webhook_ids column from installations table
    op.drop_column('installations', 'webhook_ids')
