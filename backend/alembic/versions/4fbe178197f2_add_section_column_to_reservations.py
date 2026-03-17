"""add section column to reservations

Revision ID: 4fbe178197f2
Revises: 006
Create Date: 2026-03-17 18:44:55.034231
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '4fbe178197f2'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reservations', sa.Column('section', sa.String(length=20), nullable=True))
    # Backfill: room_number가 있으면 'room', naver_room_type에 '파티만'이면 'party', 나머지 'unassigned'
    op.execute("""
        UPDATE reservations SET section = CASE
            WHEN room_number IS NOT NULL THEN 'room'
            WHEN room_info LIKE '%파티만%' THEN 'party'
            ELSE 'unassigned'
        END
    """)


def downgrade() -> None:
    op.drop_column('reservations', 'section')
