"""템플릿/스케줄 보호 게이트웨이.

두 가지 책임:

1. **잠금 가드**
   `is_locked=True` 인 템플릿·스케줄은 웹 API 로 삭제할 수 없고, 수정도 막힌다.
   단 **활성/비활성 토글(`is_active`)만은 예외로 허용**한다 — 발송 on/off 는
   문구 보호와 성격이 다른 운영 행위라, 급할 때 즉시 멈출 수 없으면 오히려 위험하다.
   해제는 DB 직접 변경으로만 가능하다 — UI 에 해제 경로를 두지 않는 것이 설계 의도.

   - `assert_update_allowed(obj, update_data, kind)`: PUT 경로 (활성 토글 예외 적용)
   - `assert_template_unlocked` / `assert_schedule_unlocked`: DELETE 경로 (전면 차단)

2. **영구 감사 + 삭제 스냅샷** (`log_template_activity`)
   기존에 CRUD 추적은 `diag()` 에만 있었고 diag 로그는 7일치만 보존된다
   (`diag_logger.py` backupCount=7). 그래서 2026-06 소실 건은 추적이 불가능했고
   2026-08-04 건도 본문을 `activity_logs` 에서 역추적해야 복구할 수 있었다.
   이 모듈은 CRUD 를 ActivityLog 로 승격하고, 삭제 시 **본문·설정 전문을 스냅샷**으로
   남겨 같은 포렌식이 다시 필요 없게 한다.

배경: docs/plans/ 없음 — 2026-08-10 반복 오삭제 사고 대응으로 신설.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from app.db.models import MessageTemplate, TemplateSchedule

# 잠금 해제는 UI 에 노출하지 않는다. 안내 문구도 그 사실을 명시한다.
_LOCKED_MSG = (
    "잠긴 {kind}입니다. 반복 오삭제 방지를 위해 웹에서 수정·삭제할 수 없습니다. "
    "변경이 필요하면 관리자에게 요청하세요."
)


# 잠겨 있어도 허용하는 필드. 발송 on/off 는 "문구 보호" 와 성격이 다른 운영 행위라
# (급할 때 즉시 멈출 수 있어야 함) 잠금에서 예외로 뺀다. 나머지 필드는 전부 차단.
_ACTIVATION_ONLY = {"is_active"}


def assert_template_unlocked(template: MessageTemplate) -> None:
    """잠긴 템플릿이면 403. 삭제 등 필드 정보가 없는 경로에서 쓴다."""
    if getattr(template, "is_locked", False):
        raise HTTPException(status_code=403, detail=_LOCKED_MSG.format(kind="템플릿"))


def assert_schedule_unlocked(schedule: TemplateSchedule) -> None:
    """잠긴 스케줄이면 403. 삭제 등 필드 정보가 없는 경로에서 쓴다."""
    if getattr(schedule, "is_locked", False):
        raise HTTPException(status_code=403, detail=_LOCKED_MSG.format(kind="스케줄"))


def assert_update_allowed(obj, update_data: dict, kind: str) -> None:
    """수정 요청 가드 — 잠겼어도 활성/비활성 토글만은 통과시킨다.

    update_data 는 `_remap_active_field` 를 거친 뒤(ORM 필드명 기준)여야 한다.
    빈 요청(변경 필드 없음)은 아무것도 바꾸지 않으므로 통과.
    """
    if not getattr(obj, "is_locked", False):
        return
    if set(update_data) - _ACTIVATION_ONLY:
        raise HTTPException(
            status_code=403,
            detail=(
                f"잠긴 {kind}입니다. 반복 오삭제 방지를 위해 활성/비활성 외에는 "
                "웹에서 수정할 수 없습니다. 변경이 필요하면 관리자에게 요청하세요."
            ),
        )


_TEMPLATE_SNAPSHOT_FIELDS = (
    "id", "template_key", "name", "short_label", "lms_title", "content",
    "variables", "category", "is_active", "is_locked", "participant_buffer",
    "male_buffer", "female_buffer", "gender_ratio_buffers", "round_unit",
    "round_mode", "sort_order",
)

_SCHEDULE_SNAPSHOT_FIELDS = (
    "id", "template_id", "schedule_name", "schedule_type", "hour", "minute",
    "day_of_week", "interval_minutes", "active_start_hour", "active_end_hour",
    "timezone", "filters", "target_mode", "exclude_sent", "is_active", "is_locked",
    "once_per_stay", "date_target", "stay_filter", "schedule_category", "custom_type",
    "hours_since_booking", "gender_filter", "max_checkin_days",
    "expires_after_days", "send_condition_date", "send_condition_ratio",
    "send_condition_operator",
)


def _snapshot(obj: Any, fields: tuple[str, ...]) -> dict:
    out: dict[str, Any] = {}
    for f in fields:
        v = getattr(obj, f, None)
        out[f] = v if (v is None or isinstance(v, (str, int, float, bool))) else str(v)
    return out


def snapshot_template(template: MessageTemplate) -> dict:
    """삭제/변경 감사용 템플릿 전문 스냅샷 (본문 포함)."""
    return _snapshot(template, _TEMPLATE_SNAPSHOT_FIELDS)


def snapshot_schedule(schedule: TemplateSchedule) -> dict:
    """삭제/변경 감사용 스케줄 전문 스냅샷."""
    return _snapshot(schedule, _SCHEDULE_SNAPSHOT_FIELDS)


def log_template_activity(
    db,
    *,
    action: str,
    kind: str,
    name: str,
    created_by: str,
    snapshot: Optional[dict] = None,
    changes: Optional[dict] = None,
) -> None:
    """템플릿/스케줄 CRUD 를 ActivityLog 에 영구 기록.

    Args:
        action: 'created' | 'updated' | 'deleted'
        kind:   '템플릿' | '스케줄'
        snapshot: 삭제 시 복구용 전문 (본문 포함). 생성/수정 시엔 생략 가능.
        changes: 수정 시 before/after diff.

    `log_activity` 는 flush 만 하고, 요청 세션은 종료 시 commit 하지 않는다
    (`database.get_db` 는 close 만 함). 따라서 이 함수가 직접 commit 해야
    생성/수정 경로의 감사 행이 유실되지 않는다. 삭제 경로에서는 실제 삭제보다
    먼저 커밋되는데, 삭제가 실패해도 감사가 남는 편이 안전하므로 의도된 순서다.

    ActivityLog 기록 실패가 본 작업(삭제/수정)을 막으면 안 되므로 예외를 삼킨다.
    """
    from app.services.activity_logger import log_activity

    labels = {"created": "생성", "updated": "수정", "deleted": "삭제"}
    detail: dict[str, Any] = {"action": action, "kind": kind, "name": name}
    if snapshot is not None:
        detail["snapshot"] = snapshot
    if changes:
        detail["changes"] = changes

    try:
        log_activity(
            db,
            type=f"template_{action}",
            title=f"{kind} {labels.get(action, action)}: {name}",
            detail=detail,
            target_count=1,
            success_count=1,
            created_by=created_by,
        )
        db.commit()
    except Exception:  # pragma: no cover — 감사 실패가 본 작업을 막지 않는다
        db.rollback()
