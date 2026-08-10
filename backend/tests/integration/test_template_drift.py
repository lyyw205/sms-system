"""스냅샷 대조 변동 감지 검증.

핵심: **경로 무관**이어야 한다 — API 를 거치지 않은 변경(DB 직접 수정)도 잡혀야
전면 잠금 이후의 유일한 감시 수단으로 기능한다.
"""
import json

from app.db.models import MessageTemplate, TemplateBaseline, TemplateSchedule
from app.services.template_drift import (
    build_snapshot,
    check_drift,
    diff_snapshots,
    fingerprint,
    has_drift,
)

TENANT_ID = 1


def _tpl(db, key="k1", name="템플릿A", content="본문", **kw):
    t = MessageTemplate(template_key=key, name=name, content=content, is_active=True, **kw)
    db.add(t)
    db.flush()
    return t


def _sch(db, tid, name="스케줄A", hour=14, **kw):
    s = TemplateSchedule(template_id=tid, schedule_name=name, schedule_type="daily",
                         hour=hour, minute=0, is_active=True, **kw)
    db.add(s)
    db.flush()
    return s


class TestBaseline:
    def test_first_run_creates_baseline_silently(self, db):
        """첫 실행에서 알림이 가면 전 항목이 '신규'로 잡혀 무의미하다."""
        _tpl(db)
        assert check_drift(db, TENANT_ID) is None
        assert db.query(TemplateBaseline).count() == 1

    def test_no_change_no_drift(self, db):
        _tpl(db)
        check_drift(db, TENANT_ID)
        assert check_drift(db, TENANT_ID) is None

    def test_baseline_is_updated_after_drift(self, db):
        """갱신 안 하면 같은 변동이 매일 반복 알림된다."""
        t = _tpl(db)
        check_drift(db, TENANT_ID)
        t.name = "이름변경"
        db.flush()
        assert check_drift(db, TENANT_ID) is not None
        assert check_drift(db, TENANT_ID) is None   # 두 번째엔 조용해야 함


class TestDetectsDirectDbChanges:
    """API 를 전혀 거치지 않은 변경도 잡혀야 한다."""

    def test_detects_direct_delete(self, db):
        t = _tpl(db)
        check_drift(db, TENANT_ID)
        db.delete(t)          # API 우회 — 직접 삭제
        db.flush()
        d = check_drift(db, TENANT_ID)
        assert len(d["removed"]) == 1
        assert d["removed"][0]["name"] == "템플릿A"

    def test_removed_entry_carries_full_snapshot_for_recovery(self, db):
        """복구가 가능해야 감시의 의미가 있다 — 본문이 실려야 한다."""
        t = _tpl(db, content="복구되어야 할 본문")
        check_drift(db, TENANT_ID)
        db.delete(t)
        db.flush()
        d = check_drift(db, TENANT_ID)
        assert d["removed"][0]["snapshot"]["content"] == "복구되어야 할 본문"

    def test_detects_direct_content_edit(self, db):
        t = _tpl(db, content="원본")
        check_drift(db, TENANT_ID)
        t.content = "몰래 수정됨"
        db.flush()
        d = check_drift(db, TENANT_ID)
        assert d["changed"][0]["fields"]["content"] == {"before": "원본", "after": "몰래 수정됨"}

    def test_detects_added(self, db):
        _tpl(db)
        check_drift(db, TENANT_ID)
        _tpl(db, key="k2", name="새템플릿")
        d = check_drift(db, TENANT_ID)
        assert [a["name"] for a in d["added"]] == ["새템플릿"]

    def test_detects_schedule_timing_change(self, db):
        t = _tpl(db)
        s = _sch(db, t.id)
        check_drift(db, TENANT_ID)
        s.hour = 3
        db.flush()
        d = check_drift(db, TENANT_ID)
        assert d["changed"][0]["fields"]["hour"] == {"before": 14, "after": 3}

    def test_detects_unlock(self, db):
        """누가 잠금을 몰래 푸는 것도 변동이다."""
        t = _tpl(db, is_locked=True)
        check_drift(db, TENANT_ID)
        t.is_locked = False
        db.flush()
        d = check_drift(db, TENANT_ID)
        assert d["changed"][0]["fields"]["is_locked"] == {"before": True, "after": False}


class TestNoFalsePositives:
    def test_updated_at_is_not_compared(self, db):
        """updated_at 을 넣으면 매일 오탐이 난다 — 스냅샷 필드에서 빠져야 한다."""
        snap = build_snapshot(db)
        _tpl(db)
        snap2 = build_snapshot(db)
        for row in snap2["templates"].values():
            assert "updated_at" not in row
            assert "created_at" not in row
        assert snap != snap2

    def test_schedule_run_timestamps_not_compared(self, db):
        t = _tpl(db)
        s = _sch(db, t.id)
        check_drift(db, TENANT_ID)
        from datetime import datetime
        s.last_run_at = datetime(2026, 8, 10, 5, 0)
        s.next_run_at = datetime(2026, 8, 11, 5, 0)
        db.flush()
        assert check_drift(db, TENANT_ID) is None   # 실행 시각 변화는 변동이 아니다

    def test_fingerprint_stable_across_calls(self, db):
        _tpl(db)
        assert fingerprint(build_snapshot(db)) == fingerprint(build_snapshot(db))


class TestDiffHelpers:
    def test_has_drift(self):
        assert not has_drift({"added": [], "removed": [], "changed": []})
        assert has_drift({"added": [{"x": 1}], "removed": [], "changed": []})

    def test_diff_on_empty_baseline(self):
        d = diff_snapshots({}, {"templates": {"1": {"name": "a"}}, "schedules": {}})
        assert len(d["added"]) == 1

    def test_baseline_snapshot_is_json_round_trippable(self, db):
        _tpl(db)
        check_drift(db, TENANT_ID)
        b = db.query(TemplateBaseline).first()
        assert json.loads(b.snapshot)["templates"]
        assert len(b.fingerprint) == 64
