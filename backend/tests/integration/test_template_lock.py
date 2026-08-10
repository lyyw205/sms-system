"""잠금(is_locked) 가드 + CRUD 감사 로그 검증.

배경: 2026-06 / 2026-08-04 두 차례 웹 UI 에서 운영 중인 템플릿·스케줄이
삭제돼 문구가 유실됐다. is_locked 는 그 재발을 막는 차단막이고,
ActivityLog 스냅샷은 diag(7일 보존) 를 대체하는 영구 복구 경로다.
"""
import json

import pytest
from fastapi import HTTPException

from app.db.models import ActivityLog, MessageTemplate, TemplateSchedule
from app.services.template_guard import (
    assert_schedule_unlocked,
    assert_template_unlocked,
    log_template_activity,
    snapshot_schedule,
    snapshot_template,
)


def _make_template(db, *, locked=False):
    t = MessageTemplate(
        template_key="k1", name="테스트 템플릿", content="본문 {{tomorrow_male_count}}",
        is_active=True, is_locked=locked, male_buffer=3, female_buffer=7,
    )
    db.add(t)
    db.flush()
    return t


def _make_schedule(db, template_id, *, locked=False):
    s = TemplateSchedule(
        template_id=template_id, schedule_name="테스트 스케줄",
        schedule_type="daily", hour=14, minute=0, is_active=True, is_locked=locked,
    )
    db.add(s)
    db.flush()
    return s


class TestLockGuard:
    def test_unlocked_template_passes(self, db):
        assert assert_template_unlocked(_make_template(db, locked=False)) is None

    def test_locked_template_raises_403(self, db):
        with pytest.raises(HTTPException) as e:
            assert_template_unlocked(_make_template(db, locked=True))
        assert e.value.status_code == 403
        assert "잠긴" in e.value.detail

    def test_unlocked_schedule_passes(self, db):
        t = _make_template(db)
        assert assert_schedule_unlocked(_make_schedule(db, t.id, locked=False)) is None

    def test_locked_schedule_raises_403(self, db):
        t = _make_template(db)
        with pytest.raises(HTTPException) as e:
            assert_schedule_unlocked(_make_schedule(db, t.id, locked=True))
        assert e.value.status_code == 403

    def test_default_is_unlocked(self, db):
        """기존 템플릿이 기본값으로 잠기면 운영이 마비된다 — 기본은 반드시 False."""
        t = MessageTemplate(template_key="k2", name="n", content="c")
        db.add(t)
        db.flush()
        assert not t.is_locked


class TestDeleteSnapshot:
    def test_template_snapshot_includes_content(self, db):
        """삭제 복구의 핵심 — 본문이 스냅샷에 들어가야 한다."""
        snap = snapshot_template(_make_template(db))
        assert snap["content"] == "본문 {{tomorrow_male_count}}"
        assert snap["template_key"] == "k1"
        assert snap["male_buffer"] == 3 and snap["female_buffer"] == 7

    def test_schedule_snapshot_includes_timing(self, db):
        t = _make_template(db)
        snap = snapshot_schedule(_make_schedule(db, t.id))
        assert snap["hour"] == 14 and snap["minute"] == 0
        assert snap["schedule_name"] == "테스트 스케줄"

    def test_snapshot_is_json_serializable(self, db):
        """ActivityLog.detail 은 json.dumps 되므로 직렬화 불가 값이 있으면 감사가 통째로 날아간다."""
        t = _make_template(db)
        json.dumps({"t": snapshot_template(t), "s": snapshot_schedule(_make_schedule(db, t.id))})


class TestActivityAudit:
    def test_delete_writes_recoverable_activity_log(self, db):
        t = _make_template(db)
        log_template_activity(
            db, action="deleted", kind="템플릿", name=t.name,
            created_by="tester", snapshot=snapshot_template(t),
        )
        row = db.query(ActivityLog).filter(ActivityLog.activity_type == "template_deleted").one()
        assert row.created_by == "tester"
        detail = json.loads(row.detail)
        assert detail["snapshot"]["content"] == "본문 {{tomorrow_male_count}}"

    def test_audit_row_survives_commit(self, db):
        """log_activity 는 flush 만 하고 요청 세션은 commit 하지 않는다 —
        헬퍼가 직접 commit 하지 않으면 생성/수정 감사가 통째로 유실된다."""
        t = _make_template(db)
        db.commit()
        log_template_activity(
            db, action="updated", kind="템플릿", name=t.name,
            created_by="tester", changes={"name": {"before": "a", "after": "b"}},
        )
        db.rollback()  # 커밋됐다면 rollback 후에도 남아 있어야 한다
        assert db.query(ActivityLog).filter(
            ActivityLog.activity_type == "template_updated"
        ).count() == 1

    def test_audit_failure_does_not_break_caller(self, db):
        """감사 실패가 삭제/수정 본 작업을 막으면 안 된다."""
        log_template_activity(
            db, action="deleted", kind="템플릿", name="x",
            created_by="tester", snapshot={"bad": object()},  # 직렬화 불가
        )
