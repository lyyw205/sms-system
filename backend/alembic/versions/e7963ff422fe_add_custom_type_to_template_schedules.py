"""add custom_type to template_schedules

Revision ID: e7963ff422fe
Revises: d8df417f1b7c
Create Date: 2026-04-15 14:20:03.723397
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e7963ff422fe'
down_revision: Union[str, None] = 'd8df417f1b7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('template_schedules', sa.Column('custom_type', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('template_schedules', 'custom_type')
