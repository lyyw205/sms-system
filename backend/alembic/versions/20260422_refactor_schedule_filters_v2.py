"""filters JSON v1 → v2 마이그레이션 + date_target checkout shift + target_mode 리네임

Revision ID: refactor_sched_v2
Revises: q2_cleanup_assigned_by
Create Date: 2026-04-22

변경 내용:
  1. template_schedules 백업 컬럼 3개 추가 (_date_target_v1_backup, _filters_v1_backup, _target_mode_v1_backup)
  2. filters JSON v1 → v2 변환 (Python 파싱, row-by-row)
     - stay_filter 컬럼값 → room assignment 필터로 이관
  3. date_target 복합 변환:
     - 'today_checkout'    → date_target='yesterday', target_mode='last_night'
     - 'tomorrow_checkout' → date_target='today',     target_mode='last_night'
  3c. target_mode 리네임:
     - 'once'     → 'first_night'
     - 'daily'    → NULL (기본 stay-coverage)
     - 'last_day' → 'last_night'
  4. checkout 스케줄의 과거 발송/실패 칩(reservation_sms_assignments.date) -1일 shift

downgrade:
  - 백업 컬럼에서 date_target / filters / target_mode 복원
  - 칩 date +1일 롤백 (checkout 스케줄 대상)
  - 백업 컬럼 drop
"""
import json
import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = 'refactor_sched_v2'
down_revision = 'q2_cleanup_assigned_by'
branch_labels = None
depends_on = None

logger = logging.getLogger('alembic.runtime.migration')

# ---------------------------------------------------------------------------
# Inline v1 → v2 normalization (filters.py 의 _normalize_to_v2 와 동일 규칙)
# alembic 은 app 의존을 피해야 하므로 코드 중복 감수.
# ---------------------------------------------------------------------------

_ASSIGNMENT_VALUES = {"room", "party", "unassigned", "unstable"}


def _is_v2_shape(filters: list) -> bool:
    has_nested = any(
        f.get("type") == "assignment" and any(
            k in f for k in ("buildings", "include_unassigned", "stay_filter")
        )
        for f in filters
    )
    has_v1_only = any(
        f.get("type") in ("building", "room", "room_assigned", "party_only")
        for f in filters
    )
    if has_nested and not has_v1_only:
        return True
    if not has_v1_only:
        return True
    return False


def _normalize_to_v2(filters: list, stay_filter_col=None) -> list:
    """Convert v1 filter list to v2.  stay_filter 컬럼 값은
    room assignment 필터가 존재할 때 해당 필터에 이관된다.

    Args:
        filters: parsed JSON list from the DB column
        stay_filter_col: value of TemplateSchedule.stay_filter column (str | None)
    """
    if not filters:
        # 필터 없고 stay_filter 만 있는 경우: room assignment 생성
        if stay_filter_col:
            room_filter: dict = {"type": "assignment", "value": "room"}
            room_filter["stay_filter"] = stay_filter_col
            return [room_filter]
        return []

    if _is_v2_shape(filters):
        # 이미 v2 — legacy alias 정리만 수행 (idempotent)
        out: list = []
        room_patched = False
        for f in filters:
            t = f.get("type")
            if t == "room":
                continue
            if t == "room_assigned":
                out.append({"type": "assignment", "value": "room"})
            elif t == "party_only":
                out.append({"type": "assignment", "value": "party"})
            else:
                out.append(dict(f))  # shallow copy

        # stay 이관: room assignment 이 있으면 첫 번째 room 에 병합
        if stay_filter_col:
            for f in out:
                if f.get("type") == "assignment" and f.get("value") == "room":
                    if stay_filter_col and "stay_filter" not in f:
                        f["stay_filter"] = stay_filter_col
                    room_patched = True
                    break
            if not room_patched and stay_filter_col:
                room_filter = {"type": "assignment", "value": "room"}
                room_filter["stay_filter"] = stay_filter_col
                out.insert(0, room_filter)
        return out

    # --- v1 변환 ---
    assignments: list[str] = []
    buildings: list[int] = []
    has_unassigned = False
    column_matches: list[dict] = []
    passthrough: list[dict] = []

    for f in filters:
        t = f.get("type")
        v = f.get("value")
        if t == "assignment":
            if v == "unassigned":
                has_unassigned = True
            elif v in _ASSIGNMENT_VALUES:
                assignments.append(v)
        elif t == "room_assigned":
            assignments.append("room")
        elif t == "party_only":
            assignments.append("party")
        elif t == "building":
            try:
                buildings.append(int(v))
            except (ValueError, TypeError):
                pass
        elif t == "room":
            continue  # ghost: drop
        elif t == "column_match":
            column_matches.append({"type": "column_match", "value": v})
        else:
            passthrough.append(f)

    out: list = []
    room_emitted = False

    if "room" in assignments or buildings:
        room_filter = {"type": "assignment", "value": "room"}
        if buildings:
            room_filter["buildings"] = sorted(set(buildings))
        if has_unassigned:
            room_filter["include_unassigned"] = True
            has_unassigned = False
        # stay 이관
        if stay_filter_col:
            room_filter["stay_filter"] = stay_filter_col
        out.append(room_filter)
        room_emitted = True

    for v in assignments:
        if v == "room":
            continue
        out.append({"type": "assignment", "value": v})

    if has_unassigned and not room_emitted:
        out.append({"type": "assignment", "value": "unassigned"})
        # stay_filter 는 unassigned 단독엔 이관 불가 → room 생성
        if stay_filter_col:
            room_filter = {"type": "assignment", "value": "room"}
            room_filter["stay_filter"] = stay_filter_col
            out.insert(0, room_filter)

    out.extend(column_matches)
    out.extend(passthrough)
    return out


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade():
    connection = op.get_bind()

    # -----------------------------------------------------------------------
    # Step 1: 백업 컬럼 추가 + 현재 값 복사
    # -----------------------------------------------------------------------
    logger.info("[refactor_sched_v2] Step 1: 백업 컬럼 추가")
    op.add_column(
        'template_schedules',
        sa.Column('_date_target_v1_backup', sa.String(30), nullable=True),
    )
    op.add_column(
        'template_schedules',
        sa.Column('_filters_v1_backup', sa.Text, nullable=True),
    )
    op.add_column(
        'template_schedules',
        sa.Column('_target_mode_v1_backup', sa.String(20), nullable=True),
    )
    connection.execute(text(
        "UPDATE template_schedules "
        "SET _date_target_v1_backup = date_target, "
        "    _filters_v1_backup = filters, "
        "    _target_mode_v1_backup = target_mode"
    ))
    logger.info("[refactor_sched_v2] Step 1: 완료")

    # -----------------------------------------------------------------------
    # Step 2: filters JSON v1 → v2 변환 (row-by-row, 손상 JSON skip)
    # -----------------------------------------------------------------------
    logger.info("[refactor_sched_v2] Step 2: filters v1 → v2 변환 시작")
    rows = connection.execute(text(
        "SELECT id, filters, stay_filter FROM template_schedules"
    )).fetchall()

    updated_count = 0
    skipped_count = 0

    for row in rows:
        row_id = row[0]
        raw_filters = row[1]
        stay_filter_col = row[2]      # str | None

        # JSON 파싱
        parsed: list = []
        if raw_filters:
            try:
                parsed = json.loads(raw_filters)
                if not isinstance(parsed, list):
                    raise ValueError("filters 가 list 가 아님")
            except Exception as exc:
                logger.warning(
                    "[refactor_sched_v2] id=%s filters 파싱 실패, skip: %s", row_id, exc
                )
                skipped_count += 1
                continue

        try:
            v2 = _normalize_to_v2(parsed, stay_filter_col=stay_filter_col)
        except Exception as exc:
            logger.warning(
                "[refactor_sched_v2] id=%s normalize 실패, skip: %s", row_id, exc
            )
            skipped_count += 1
            continue

        new_filters_json = json.dumps(v2, ensure_ascii=False)
        connection.execute(
            text("UPDATE template_schedules SET filters = :f WHERE id = :id"),
            {"f": new_filters_json, "id": row_id},
        )
        updated_count += 1

    logger.info(
        "[refactor_sched_v2] Step 2: 완료 — updated=%d skipped=%d",
        updated_count, skipped_count,
    )

    # -----------------------------------------------------------------------
    # Step 3a: date_target + target_mode 복합 UPDATE
    # 먼저 checkout 스케줄 id 리스트 확보 (UPDATE 이전에)
    # -----------------------------------------------------------------------
    logger.info("[refactor_sched_v2] Step 3: date_target checkout shift 시작")

    checkout_rows = connection.execute(text(
        "SELECT id FROM template_schedules "
        "WHERE date_target IN ('today_checkout', 'tomorrow_checkout')"
    )).fetchall()
    checkout_schedule_ids = [r[0] for r in checkout_rows]
    logger.info(
        "[refactor_sched_v2] checkout 스케줄 %d건: %s",
        len(checkout_schedule_ids), checkout_schedule_ids,
    )

    connection.execute(text(
        "UPDATE template_schedules "
        "SET date_target = 'yesterday', target_mode = 'last_night' "
        "WHERE date_target = 'today_checkout'"
    ))
    connection.execute(text(
        "UPDATE template_schedules "
        "SET date_target = 'today', target_mode = 'last_night' "
        "WHERE date_target = 'tomorrow_checkout'"
    ))
    logger.info("[refactor_sched_v2] Step 3a: date_target 변환 완료")

    # -----------------------------------------------------------------------
    # Step 3c: target_mode 리네임 (once → first_night, daily → NULL, last_day → last_night)
    # Step 3a 에서 already last_night 으로 변환된 checkout 스케줄은 건드리지 않음
    # -----------------------------------------------------------------------
    connection.execute(text("UPDATE template_schedules SET target_mode='first_night' WHERE target_mode='once'"))
    connection.execute(text("UPDATE template_schedules SET target_mode=NULL WHERE target_mode='daily'"))
    connection.execute(text("UPDATE template_schedules SET target_mode='last_night' WHERE target_mode='last_day'"))
    logger.info("[refactor_sched_v2] Step 3c: target_mode 리네임 완료")

    # -----------------------------------------------------------------------
    # Step 3d: is_once_per_stay=true 이면서 target_mode=NULL 인 스케줄은
    # target_mode='first_night' 로 승격 (그룹 dedup 을 target_mode 가 처리)
    # -----------------------------------------------------------------------
    connection.execute(text(
        "UPDATE template_schedules "
        "SET target_mode='first_night' "
        "WHERE is_once_per_stay = true AND target_mode IS NULL"
    ))
    logger.info("[refactor_sched_v2] Step 3d: once_per_stay → first_night 승격 완료")

    # -----------------------------------------------------------------------
    # Step 3b: 과거 발송/실패 칩 date -1일 shift (checkout_schedule_ids 만)
    # -----------------------------------------------------------------------
    if checkout_schedule_ids:
        if connection.dialect.name == 'postgresql':
            connection.execute(
                text(
                    "UPDATE reservation_sms_assignments "
                    "SET date = (date::date - 1)::text "
                    "WHERE schedule_id = ANY(:ids) "
                    "AND (sent_at IS NOT NULL OR send_status = 'failed')"
                ),
                {"ids": checkout_schedule_ids},
            )
        else:
            # SQLite: date 컬럼은 VARCHAR YYYY-MM-DD 형식
            connection.execute(
                text(
                    "UPDATE reservation_sms_assignments "
                    "SET date = date(date, '-1 day') "
                    "WHERE schedule_id IN :ids "
                    "AND (sent_at IS NOT NULL OR send_status = 'failed')"
                ).bindparams(sa.bindparam('ids', expanding=True)),
                {"ids": checkout_schedule_ids},
            )
        logger.info("[refactor_sched_v2] Step 3b: 칩 date -1일 shift 완료")
    else:
        logger.info("[refactor_sched_v2] Step 3b: checkout 스케줄 없음, skip")

    logger.info("[refactor_sched_v2] upgrade 완료")


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------

def downgrade():
    connection = op.get_bind()

    logger.info("[refactor_sched_v2] downgrade 시작")

    # -----------------------------------------------------------------------
    # 칩 date +1일 롤백: 현재 date_target 이 아직 변환 후 값이므로
    # 백업 컬럼(_date_target_v1_backup)에서 checkout 스케줄 id 찾기
    # -----------------------------------------------------------------------
    checkout_rows = connection.execute(text(
        "SELECT id FROM template_schedules "
        "WHERE _date_target_v1_backup IN ('today_checkout', 'tomorrow_checkout')"
    )).fetchall()
    checkout_schedule_ids = [r[0] for r in checkout_rows]

    if checkout_schedule_ids:
        logger.info(
            "[refactor_sched_v2] downgrade: 칩 date +1일 롤백 대상 %d건",
            len(checkout_schedule_ids),
        )
        if connection.dialect.name == 'postgresql':
            connection.execute(
                text(
                    "UPDATE reservation_sms_assignments "
                    "SET date = (date::date + 1)::text "
                    "WHERE schedule_id = ANY(:ids) "
                    "AND (sent_at IS NOT NULL OR send_status = 'failed')"
                ),
                {"ids": checkout_schedule_ids},
            )
        else:
            connection.execute(
                text(
                    "UPDATE reservation_sms_assignments "
                    "SET date = date(date, '+1 day') "
                    "WHERE schedule_id IN :ids "
                    "AND (sent_at IS NOT NULL OR send_status = 'failed')"
                ).bindparams(sa.bindparam('ids', expanding=True)),
                {"ids": checkout_schedule_ids},
            )

    # -----------------------------------------------------------------------
    # date_target 백업에서 복원
    # -----------------------------------------------------------------------
    op.execute(text(
        "UPDATE template_schedules "
        "SET date_target = _date_target_v1_backup "
        "WHERE _date_target_v1_backup IS NOT NULL"
    ))

    # -----------------------------------------------------------------------
    # filters 백업에서 복원
    # -----------------------------------------------------------------------
    op.execute(text(
        "UPDATE template_schedules "
        "SET filters = _filters_v1_backup "
        "WHERE _filters_v1_backup IS NOT NULL"
    ))

    # -----------------------------------------------------------------------
    # target_mode 백업에서 복원
    # -----------------------------------------------------------------------
    op.execute(text(
        "UPDATE template_schedules "
        "SET target_mode = _target_mode_v1_backup "
        "WHERE _target_mode_v1_backup IS NOT NULL"
    ))

    # -----------------------------------------------------------------------
    # 백업 컬럼 drop
    # -----------------------------------------------------------------------
    op.drop_column('template_schedules', '_filters_v1_backup')
    op.drop_column('template_schedules', '_date_target_v1_backup')
    op.drop_column('template_schedules', '_target_mode_v1_backup')

    logger.info("[refactor_sched_v2] downgrade 완료")
