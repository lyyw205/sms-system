"""tenants.room_settings_locked — 객실 설정 잠금 (테넌트 스위치)

2026-09-01 스테이블 객실 파괴 사건 대응. template_guard(023) 와 같은 철학의
관문을 객실·그룹·건물·상품메타로 확장한다. 해제는 DB 직접 변경으로만.

Revision ID: 025
Revises: 024
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision = '025'
down_revision: Union[str, None] = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # init_db 자동 마이그레이션과 이중화돼 있어(G-5 기간 준수사항) 존재 검사 후 추가
    cols = [c["name"] for c in sa.inspect(op.get_bind()).get_columns("tenants")]
    if "room_settings_locked" not in cols:
        op.add_column(
            "tenants",
            sa.Column("room_settings_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column("tenants", "room_settings_locked")
