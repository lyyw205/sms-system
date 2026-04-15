"""add send_status and send_error to reservation_sms_assignments

Revision ID: 1aed93f2637e
Revises: e7963ff422fe
Create Date: 2026-04-15 16:43:26.685120
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '1aed93f2637e'
down_revision: Union[str, None] = 'e7963ff422fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reservation_sms_assignments', sa.Column('send_status', sa.String(length=10), nullable=True))
    op.add_column('reservation_sms_assignments', sa.Column('send_error', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('reservation_sms_assignments', 'send_error')
    op.drop_column('reservation_sms_assignments', 'send_status')
