"""Add assigned_by column to room_assignments

Revision ID: 006
Revises: 005
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('room_assignments', sa.Column('assigned_by', sa.String(10), server_default='auto'))


def downgrade() -> None:
    op.drop_column('room_assignments', 'assigned_by')
