"""Add gender_manual to reservations

Revision ID: aceea3667c87
Revises: 016
Create Date: 2026-04-01 10:16:41.841222
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'aceea3667c87'
down_revision: Union[str, None] = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reservations', sa.Column('gender_manual', sa.Boolean(), server_default=sa.text('false'), nullable=True))


def downgrade() -> None:
    op.drop_column('reservations', 'gender_manual')
