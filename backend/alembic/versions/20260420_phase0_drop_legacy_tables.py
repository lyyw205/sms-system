"""phase0: drop legacy tables (campaign_logs, rules, documents, gender_stats) + Tenant.snapshot_refresh_times

Revision ID: phase0_legacy_drop
Revises: 1aed93f2637e
Create Date: 2026-04-20

사전조사 결과: 모든 테이블 0건 + snapshot_refresh_times 읽기 0건 확인됨. 안전하게 DROP.
"""
from alembic import op
import sqlalchemy as sa

revision = 'phase0_legacy_drop'
down_revision = '1aed93f2637e'
branch_labels = None
depends_on = None


def upgrade():
    # 4개 legacy 테이블 DROP
    op.drop_table('campaign_logs')
    op.drop_table('rules')
    op.drop_table('documents')
    op.drop_table('gender_stats')
    # dead column DROP
    op.drop_column('tenants', 'snapshot_refresh_times')


def downgrade():
    # 롤백: 테이블 구조만 복원 (데이터는 복원 안 됨)
    op.add_column('tenants',
        sa.Column('snapshot_refresh_times', sa.Text(), nullable=True))

    op.create_table('gender_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.String(length=20), nullable=False),
        sa.Column('male_count', sa.Integer(), nullable=True),
        sa.Column('female_count', sa.Integer(), nullable=True),
        sa.Column('total_participants', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('is_indexed', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('pattern', sa.String(length=500), nullable=False),
        sa.Column('response', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('campaign_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('campaign_type', sa.String(length=50), nullable=False),
        sa.Column('target_tag', sa.String(length=50), nullable=True),
        sa.Column('target_count', sa.Integer(), nullable=True),
        sa.Column('sent_count', sa.Integer(), nullable=True),
        sa.Column('failed_count', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
