"""Remove sms_type from template_schedules

Revision ID: 005
Revises: 004
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('template_schedules', 'sms_type')


def downgrade() -> None:
    op.add_column('template_schedules', sa.Column('sms_type', sa.String(20), server_default='room'))
