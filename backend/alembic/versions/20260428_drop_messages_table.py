"""drop messages table (legacy auto-response pipeline removed)

Revision ID: drop_messages_table
Revises: surcharge_v2
Create Date: 2026-04-28

배경: 자동응답 파이프라인(rules/documents/llm)은 phase0 에서 제거됐지만
messages 테이블만 잔존. messages.py 라우터/Message 모델 제거에 맞춰 테이블도 DROP.
사전조사: messages 테이블에 대한 INSERT/UPDATE 경로 0건 (라우터 제거 이후).
"""
from alembic import op
import sqlalchemy as sa


revision = 'drop_messages_table'
down_revision = 'surcharge_v2'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('messages')


def downgrade():
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.String(length=100), nullable=True),
        sa.Column('direction', sa.String(length=20), nullable=False),
        sa.Column('from_phone', sa.String(length=20), nullable=False),
        sa.Column('to', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('auto_response', sa.Text(), nullable=True),
        sa.Column('auto_response_confidence', sa.Float(), nullable=True),
        sa.Column('is_needs_review', sa.Boolean(), nullable=True),
        sa.Column('response_source', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'message_id', name='uq_tenant_message_id'),
    )
    op.create_index('ix_messages_direction', 'messages', ['direction'])
    op.create_index('ix_messages_from_phone', 'messages', ['from_phone'])
    op.create_index('ix_messages_to', 'messages', ['to'])
    op.create_index('ix_messages_is_needs_review', 'messages', ['is_needs_review'])
    op.create_index('ix_messages_response_source', 'messages', ['response_source'])
    op.create_index('ix_messages_tenant_id', 'messages', ['tenant_id'])
