"""surcharge 시스템 4-level → 2-type 재설계

Revision ID: surcharge_v2
Revises: refactor_sched_v2
Create Date: 2026-04-22

변경 내용:
  1. Tenant 테이블에 surcharge_unit_standard / surcharge_unit_double 컬럼 추가
  2. 템플릿 key 변경: id=24 → add_standard, id=25 → add_double
  3. 기존 칩의 template_key 동기화
  4. 구 템플릿 id=22, 23 비활성화
  5. 구 standard 스케줄 id=17~20 비활성화 (custom_schedule 로 대체)
  6. 구 비활성 custom_schedule id=116, 117, 118 삭제 + 관련 미발송 칩 삭제
"""
import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = 'surcharge_v2'
down_revision = 'refactor_sched_v2'
branch_labels = None
depends_on = None

logger = logging.getLogger('alembic.runtime.migration')


def upgrade():
    conn = op.get_bind()

    # 1. Tenant 컬럼 2개 추가 (idempotent — init_db auto-migrate 와 충돌 방지)
    from sqlalchemy import inspect
    insp = inspect(conn)
    tenant_cols = {c['name'] for c in insp.get_columns('tenants')}
    if 'surcharge_unit_standard' not in tenant_cols:
        op.add_column('tenants', sa.Column(
            'surcharge_unit_standard', sa.Integer(), nullable=False, server_default='20000'
        ))
        logger.info("surcharge_v2: tenants.surcharge_unit_standard 컬럼 추가")
    else:
        logger.info("surcharge_v2: tenants.surcharge_unit_standard 이미 존재, skip")
    if 'surcharge_unit_double' not in tenant_cols:
        op.add_column('tenants', sa.Column(
            'surcharge_unit_double', sa.Integer(), nullable=False, server_default='25000'
        ))
        logger.info("surcharge_v2: tenants.surcharge_unit_double 컬럼 추가")
    else:
        logger.info("surcharge_v2: tenants.surcharge_unit_double 이미 존재, skip")

    # 2. 템플릿 key 변경 (id=24: add_one_person → add_standard)
    row = conn.execute(text("SELECT id FROM message_templates WHERE id=24")).fetchone()
    if row:
        conn.execute(text(
            "UPDATE message_templates SET key='add_standard', name='인원 초과 (일반 객실)' WHERE id=24"
        ))
        logger.info("surcharge_v2: id=24 key → add_standard")

    # 3a. 템플릿 key 변경 (id=25: add_one_person_to_twin → add_double)
    row = conn.execute(text("SELECT id FROM message_templates WHERE id=25")).fetchone()
    if row:
        conn.execute(text(
            "UPDATE message_templates SET key='add_double', name='인원 초과 (더블 객실)' WHERE id=25"
        ))
        logger.info("surcharge_v2: id=25 key → add_double")

    # 3b. 기존 칩의 template_key 동기화
    conn.execute(text(
        "UPDATE reservation_sms_assignments SET template_key='add_standard' "
        "WHERE template_key='add_one_person'"
    ))
    conn.execute(text(
        "UPDATE reservation_sms_assignments SET template_key='add_double' "
        "WHERE template_key='add_one_person_to_twin'"
    ))

    # 4. 구 템플릿 id=22, 23 (add_three_person, add_two_person) 비활성화
    conn.execute(text(
        "UPDATE message_templates SET is_active=false WHERE id IN (22, 23)"
    ))
    logger.info("surcharge_v2: id=22,23 비활성화")

    # 5. 구 standard 스케줄 id=17~20 비활성화
    conn.execute(text(
        "UPDATE template_schedules SET is_active=false WHERE id IN (17, 18, 19, 20)"
    ))
    logger.info("surcharge_v2: schedule id=17~20 비활성화")

    # 6. 구 비활성 custom_schedule id=116, 117, 118 삭제 + 관련 미발송 칩 삭제
    conn.execute(text(
        "DELETE FROM reservation_sms_assignments "
        "WHERE schedule_id IN (116, 117, 118) AND sent_at IS NULL"
    ))
    conn.execute(text(
        "DELETE FROM template_schedules WHERE id IN (116, 117, 118)"
    ))
    logger.info("surcharge_v2: schedule id=116~118 + 미발송 칩 삭제")


def downgrade():
    conn = op.get_bind()

    # 6역. 삭제된 116/117/118 복원 불가 — 데이터 손실 감수
    logger.warning(
        "surcharge_v2 downgrade: schedule id=116~118 은 복원 불가 (데이터 손실)"
    )

    # 5역. 스케줄 id=17~20 재활성화
    conn.execute(text(
        "UPDATE template_schedules SET is_active=true WHERE id IN (17, 18, 19, 20)"
    ))

    # 4역. 템플릿 id=22, 23 재활성화
    conn.execute(text(
        "UPDATE message_templates SET is_active=true WHERE id IN (22, 23)"
    ))

    # 3b역. 칩 template_key 복원
    conn.execute(text(
        "UPDATE reservation_sms_assignments SET template_key='add_one_person' "
        "WHERE template_key='add_standard'"
    ))
    conn.execute(text(
        "UPDATE reservation_sms_assignments SET template_key='add_one_person_to_twin' "
        "WHERE template_key='add_double'"
    ))

    # 3a역. 템플릿 key 복원 (id=25)
    row = conn.execute(text("SELECT id FROM message_templates WHERE id=25")).fetchone()
    if row:
        conn.execute(text(
            "UPDATE message_templates SET key='add_one_person_to_twin', name='추가 인원 (더블룸)' WHERE id=25"
        ))

    # 2역. 템플릿 key 복원 (id=24)
    row = conn.execute(text("SELECT id FROM message_templates WHERE id=24")).fetchone()
    if row:
        conn.execute(text(
            "UPDATE message_templates SET key='add_one_person', name='추가 인원 1인' WHERE id=24"
        ))

    # 1역. Tenant 컬럼 제거
    op.drop_column('tenants', 'surcharge_unit_double')
    op.drop_column('tenants', 'surcharge_unit_standard')
