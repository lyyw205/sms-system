"""Add is_locked to message_templates / template_schedules

잠긴 템플릿·스케줄은 웹 API(PUT/DELETE)로 수정·삭제할 수 없다.
해제는 DB 직접 변경으로만 가능 — 반복된 오삭제 사고(2026-06, 2026-08-04)에 대한 차단막.

Revision ID: 023
Revises: 022
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision = '023'
down_revision: Union[str, None] = '022'
branch_labels = None
depends_on = None

_TABLES = ("message_templates", "template_schedules")


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table in _TABLES:
        cols = [c["name"] for c in inspector.get_columns(table)]
        if "is_locked" not in cols:
            op.add_column(
                table,
                sa.Column("is_locked", sa.Boolean(), nullable=False,
                          server_default=sa.false()),
            )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table in _TABLES:
        cols = [c["name"] for c in inspector.get_columns(table)]
        if "is_locked" in cols:
            op.drop_column(table, "is_locked")
