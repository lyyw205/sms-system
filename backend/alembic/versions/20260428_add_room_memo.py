"""add room_memo column to rooms

Revision ID: add_room_memo
Revises: drop_messages_table
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_room_memo'
down_revision = 'drop_messages_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rooms', sa.Column('room_memo', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('rooms', 'room_memo')
