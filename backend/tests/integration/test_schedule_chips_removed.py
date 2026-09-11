"""스케줄 수정 시 취소되는 예정 발송(칩) 집계·감사 검증.

배경: 스케줄을 끄거나 필터를 좁히면 reconcile 이 미발송 칩을 지우는데,
지금까지 흔적이 없어 "예정 발송이 왜 사라졌나" 를 추적할 수 없었다.
update_schedule 은 지워질 칩을 스냅샷해 응답(chips_removed)과
ActivityLog(schedule_chips_removed) 에 남긴다. 칩 보호 규칙
(sent_at 있음 / assigned_by='manual') 은 그대로 지켜져야 한다.
"""
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.template_schedules import TemplateScheduleUpdate, update_schedule
from app.db.models import (
    ActivityLog, MessageTemplate, ReservationSmsAssignment, TemplateSchedule, UserRole,
)

_ADMIN = SimpleNamespace(username="tester", role=UserRole.ADMIN)
_SUPER = SimpleNamespace(username="boss", role=UserRole.SUPERADMIN)


def _mk_schedule(db, *, locked=False, active=True):
    t = MessageTemplate(template_key="k1", name="템플릿", content="본문", is_active=True)
    db.add(t)
    db.flush()
    s = TemplateSchedule(
        template_id=t.id, schedule_name="스케줄", schedule_type="daily",
        hour=10, minute=0, is_active=active, is_locked=locked,
    )
    db.add(s)
    db.flush()
    return t, s


def _mk_chip(db, s, t, rid, date, **kw):
    chip = ReservationSmsAssignment(
        reservation_id=rid, template_key=t.template_key, date=date,
        schedule_id=s.id, **kw,
    )
    db.add(chip)
    db.flush()
    return chip


def _update(db, s, payload, user=_ADMIN):
    return update_schedule(s.id, TemplateScheduleUpdate(**payload), db, user)


class TestChipsRemovedReport:
    def test_deactivate_counts_removed_unsent_auto_chips_only(self, db):
        """끄면 미발송 auto 칩만 집계된다 — sent/manual 은 보호되고 집계에서도 빠진다."""
        t, s = _mk_schedule(db)
        _mk_chip(db, s, t, 11, "2026-09-20", assigned_by="auto")
        _mk_chip(db, s, t, 12, "2026-09-21", assigned_by="auto")
        sent = _mk_chip(db, s, t, 13, "2026-09-19", assigned_by="auto",
                        sent_at=datetime(2026, 9, 19, 10, 0))
        manual = _mk_chip(db, s, t, 14, "2026-09-22", assigned_by="manual")

        resp = _update(db, s, {"active": False})

        assert resp["chips_removed"] == 2
        remaining = {c.id for c in db.query(ReservationSmsAssignment).all()}
        assert sent.id in remaining, "발송 완료 칩 보존"
        assert manual.id in remaining, "manual 칩 보존"

        row = db.query(ActivityLog).filter(
            ActivityLog.activity_type == "schedule_chips_removed").one()
        detail = json.loads(row.detail)
        assert detail["removed_total"] == 2
        assert {c["reservation_id"] for c in detail["removed_chips"]} == {11, 12}

    def test_non_filter_field_change_reports_zero_and_keeps_chips(self, db):
        t, s = _mk_schedule(db)
        _mk_chip(db, s, t, 11, "2026-09-20", assigned_by="auto")
        resp = _update(db, s, {"schedule_name": "이름만 변경"})
        assert resp["chips_removed"] == 0
        assert db.query(ReservationSmsAssignment).count() == 1
        assert db.query(ActivityLog).filter(
            ActivityLog.activity_type == "schedule_chips_removed").count() == 0

    def test_locked_schedule_toggle_superadmin_only(self, db):
        """잠긴 스케줄 켬/끔은 SUPERADMIN 전용 가드와 chips_removed 가 함께 동작."""
        t, s = _mk_schedule(db, locked=True)
        _mk_chip(db, s, t, 11, "2026-09-20", assigned_by="auto")

        with pytest.raises(HTTPException) as e:
            _update(db, s, {"active": False}, user=_ADMIN)
        assert e.value.status_code == 403
        assert db.query(ReservationSmsAssignment).count() == 1, "거부 시 칩 무변경"

        resp = _update(db, s, {"active": False}, user=_SUPER)
        assert resp["chips_removed"] == 1
