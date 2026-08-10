"""Add template_baselines (변동 감지용 기준 스냅샷)

API 훅은 웹 경로만 잡는다. 전면 잠금 이후 실질 변경 경로인 DB 직접 변경을
잡으려면 결과 상태를 주기적으로 대조해야 한다.

Revision ID: 024
Revises: 023
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision = '024'
down_revision: Union[str, None] = '023'
branch_labels = None
depends_on = None

_TABLE = "template_baselines"


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
