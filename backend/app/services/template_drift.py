"""템플릿/스케줄 변동 감지 — 경로 무관 스냅샷 대조.

## 왜 필요한가

API CRUD 훅(`template_guard.log_template_activity`)은 **웹을 통한 변경만** 잡는다.
그런데 전면 잠금(2026-08-10) 이후 stable 의 실질적인 변경 경로는 **DB 직접 변경**
하나뿐이고, 그건 API 를 타지 않으므로 감사 로그에도 디스코드에도 남지 않는다.
즉 가장 빈번한 경로가 통째로 사각지대다.

이 모듈은 **주기적으로 전체 상태를 스냅샷 떠서 직전과 비교**한다. 변경이 어떤
경로로 일어났든(웹/DB 직접/수동 SQL/마이그레이션) 결과가 다르면 잡힌다.

## 부수 효과: 연속 백업

스냅샷에 본문 전문이 들어가므로, 누가 DB 에서 통째로 지워도 직전 스냅샷에서
복구할 수 있다. 2026-08-04 건처럼 발송 기록을 역추적할 필요가 없어진다.

## 첫 실행

베이스라인이 없으면 조용히 만들고 알리지 않는다 (전 항목이 "신규"로 잡혀
의미 없는 알림이 가는 것을 막는다).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from app.db.models import MessageTemplate, TemplateBaseline, TemplateSchedule

logger = logging.getLogger(__name__)

# 대조할 필드 — 표시용/자동갱신 필드(updated_at, last_run_at, next_run_at)는
# 매번 바뀌므로 제외한다. 넣으면 매일 오탐이 난다.
_TEMPLATE_FIELDS = (
    "template_key", "name", "short_label", "lms_title", "content", "category",
    "is_active", "is_locked", "participant_buffer", "male_buffer", "female_buffer",
    "gender_ratio_buffers", "round_unit", "round_mode",
)
_SCHEDULE_FIELDS = (
    "schedule_name", "template_id", "schedule_type", "hour", "minute", "day_of_week",
    "interval_minutes", "active_start_hour", "active_end_hour", "timezone", "filters",
    "target_mode", "exclude_sent", "is_active", "is_locked", "once_per_stay",
    "date_target", "stay_filter", "schedule_category", "custom_type",
    "hours_since_booking", "gender_filter", "max_checkin_days", "expires_after_days",
    "send_condition_date", "send_condition_ratio", "send_condition_operator",
)


def _row(obj: Any, fields: tuple[str, ...]) -> dict:
    out = {}
    for f in fields:
        v = getattr(obj, f, None)
        out[f] = v if (v is None or isinstance(v, (str, int, float, bool))) else str(v)
    return out


def build_snapshot(db) -> dict:
    """현재 테넌트의 템플릿·스케줄 전체 상태. db 는 tenant-scoped session."""
    templates = {
        str(t.id): _row(t, _TEMPLATE_FIELDS)
        for t in db.query(MessageTemplate).all()
    }
    schedules = {
        str(s.id): _row(s, _SCHEDULE_FIELDS)
        for s in db.query(TemplateSchedule).all()
    }
    return {"templates": templates, "schedules": schedules}


def fingerprint(snapshot: dict) -> str:
    blob = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def diff_snapshots(old: dict, new: dict) -> dict:
    """{'added': [...], 'removed': [...], 'changed': [...]} 형태로 변동 산출."""
    result = {"added": [], "removed": [], "changed": []}

    for section, kind in (("templates", "템플릿"), ("schedules", "스케줄")):
        o, n = old.get(section, {}) or {}, new.get(section, {}) or {}
        name_key = "name" if section == "templates" else "schedule_name"

        for oid in sorted(set(n) - set(o), key=lambda x: int(x)):
            result["added"].append({"kind": kind, "id": oid, "name": n[oid].get(name_key)})

        for oid in sorted(set(o) - set(n), key=lambda x: int(x)):
            # 삭제 건은 복구를 위해 직전 값 전체를 함께 싣는다
            result["removed"].append(
                {"kind": kind, "id": oid, "name": o[oid].get(name_key), "snapshot": o[oid]}
            )

        for oid in sorted(set(o) & set(n), key=lambda x: int(x)):
            fields = {
                f: {"before": o[oid].get(f), "after": n[oid].get(f)}
                for f in set(o[oid]) | set(n[oid])
                if o[oid].get(f) != n[oid].get(f)
            }
            if fields:
                result["changed"].append(
                    {"kind": kind, "id": oid, "name": n[oid].get(name_key), "fields": fields}
                )

    return result


def has_drift(d: dict) -> bool:
    return bool(d["added"] or d["removed"] or d["changed"])


def check_drift(db, tenant_id: int, *, tenant_slug: Optional[str] = None) -> Optional[dict]:
    """스냅샷 대조 후 베이스라인 갱신. 변동이 있으면 diff, 없으면 None.

    첫 실행(베이스라인 없음)은 베이스라인만 만들고 None 을 반환한다.
    """
    snapshot = build_snapshot(db)
    fp = fingerprint(snapshot)

    baseline = db.query(TemplateBaseline).filter(
        TemplateBaseline.tenant_id == tenant_id
    ).first()

    if baseline is None:
        db.add(TemplateBaseline(tenant_id=tenant_id, fingerprint=fp,
                                snapshot=json.dumps(snapshot, ensure_ascii=False)))
        db.commit()
        logger.info("[%s] template baseline created (%d templates, %d schedules)",
                    tenant_slug or tenant_id, len(snapshot["templates"]), len(snapshot["schedules"]))
        return None

    if baseline.fingerprint == fp:
        return None

    try:
        old = json.loads(baseline.snapshot) if baseline.snapshot else {}
    except (ValueError, TypeError):
        old = {}

    d = diff_snapshots(old, snapshot)

    baseline.fingerprint = fp
    baseline.snapshot = json.dumps(snapshot, ensure_ascii=False)
    db.commit()

    return d if has_drift(d) else None
