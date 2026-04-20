"""q2: assigned_by 'admin' 등 비표준 값을 'manual'로 정리

Revision ID: q2_cleanup_assigned_by
Revises: phase0_legacy_drop
Create Date: 2026-04-20

사전조사 결과 운영 DB에 'admin' 1건만 존재. B-3 버그 흔적 정리.
ActivityLog 보존은 raw SQL로 수행 (마이그레이션에서 ORM 사용 지양).
"""
from alembic import op
from sqlalchemy import text
import json
from datetime import datetime, timezone

revision = 'q2_cleanup_assigned_by'
down_revision = 'phase0_legacy_drop'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # 1. 영향받는 레코드 분포 조회 (tenant별 그룹화)
    result = connection.execute(text(
        "SELECT assigned_by, COUNT(*) as cnt, "
        "COALESCE(tenant_id, 0) as tid "
        "FROM room_assignments "
        "WHERE assigned_by NOT IN ('auto', 'manual') "
        "GROUP BY assigned_by, tenant_id"
    ))
    rows = result.fetchall()

    if not rows:
        return

    # 2. ActivityLog에 원본 분포 보존 (idempotent: 이미 기록됐으면 skip)
    existing_log = connection.execute(text(
        "SELECT id FROM activity_logs "
        "WHERE type = 'assigned_by_migration' LIMIT 1"
    )).fetchone()

    if not existing_log:
        tenant_groups: dict = {}
        for row in rows:
            # row: (assigned_by, cnt, tid)
            original_value, cnt, tid = row[0], row[1], row[2]
            tid = tid if tid else None
            tenant_groups.setdefault(tid, []).append({
                "original_value": original_value,
                "count": cnt,
            })

        for tid, values in tenant_groups.items():
            if tid is None:
                # tenant_id 없는 레코드는 ActivityLog 기록 skip
                # (activity_logs.tenant_id NOT NULL)
                continue
            detail_json = json.dumps({"original_distribution": values})
            connection.execute(
                text(
                    "INSERT INTO activity_logs "
                    "(tenant_id, type, title, detail, status, "
                    " target_count, success_count, failed_count, "
                    " created_at, created_by) "
                    "VALUES (:tid, 'assigned_by_migration', "
                    " 'assigned_by 필드 정리 (B-3 버그 수정)', "
                    " :detail, 'success', :cnt, :cnt, 0, :now, 'migration')"
                ),
                {
                    "tid": tid,
                    "detail": detail_json,
                    "cnt": sum(v["count"] for v in values),
                    "now": datetime.now(timezone.utc),
                }
            )

    # 3. 실제 UPDATE
    connection.execute(text(
        "UPDATE room_assignments "
        "SET assigned_by = 'manual' "
        "WHERE assigned_by NOT IN ('auto', 'manual')"
    ))


def downgrade():
    # 원본 값 손실 — 복원 불가. skip.
    pass
