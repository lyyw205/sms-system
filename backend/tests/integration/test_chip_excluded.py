"""운영자가 체크해제(excluded)한 칩 — 상태 전이 + 모든 발송 경로 차단.

회귀 배경 (2026-10-04, 예약 13719):
  - 12:47 party_info 체크해제 → 13:00 스케줄러가 그대로 발송 (발송 경로가 excluded 를 몰랐음)
  - 13:34 재체크 → 409 "이미 배정된 템플릿입니다" (excluded 행을 활성 중복으로 취급)
"""
import asyncio
from datetime import date, timedelta

from app.config import today_kst
from app.db.models import (
    MessageTemplate,
    Reservation,
    ReservationSmsAssignment,
    ReservationStatus,
    TemplateSchedule,
)
from app.scheduler.template_scheduler import TemplateScheduleExecutor
from app.services.chip_store import assign_manual_chip, exclude_chip
from app.services.sms_sender import SmsSender


# ════════════════════════════════════════════════════════════════════
# 헬퍼
# ════════════════════════════════════════════════════════════════════

class MockSMSProvider:
    def __init__(self):
        self.calls = []

    async def send_sms(self, to, message, **kwargs):
        self.calls.append(to)
        return {"success": True, "message_id": "mock", "error": None}


def _executor(db):
    return TemplateScheduleExecutor(db, tenant=None)


def _make_template(db, key="party_info"):
    tpl = MessageTemplate(
        tenant_id=1, template_key=key, name=key, content="hello", is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _make_schedule(db, template, **kwargs):
    fields = dict(
        tenant_id=1, template_id=template.id, schedule_name="test",
        schedule_type="daily", hour=13, minute=0, is_active=True,
    )
    fields.update(kwargs)
    sched = TemplateSchedule(**fields)
    db.add(sched)
    db.flush()
    return sched


def _make_reservation(db, *, check_in=None, phone="01012345678", confirmed_at=None):
    res = Reservation(
        tenant_id=1, customer_name="손님", phone=phone,
        check_in_date=check_in or today_kst(), check_in_time="15:00",
        status=ReservationStatus.CONFIRMED,
        confirmed_at=confirmed_at,
    )
    db.add(res)
    db.flush()
    return res


def _make_chip(db, res, template_key, *, date_str=None, assigned_by="auto", schedule_id=None):
    chip = ReservationSmsAssignment(
        tenant_id=1, reservation_id=res.id, template_key=template_key,
        date=date_str if date_str is not None else today_kst(),
        assigned_by=assigned_by, schedule_id=schedule_id,
    )
    db.add(chip)
    db.flush()
    return chip


# ════════════════════════════════════════════════════════════════════
# 상태 전이 — 체크해제 / 재체크
# ════════════════════════════════════════════════════════════════════

class TestExcludeAndReassign:
    def test_exclude_marks_and_clears_send_state(self, db):
        res = _make_reservation(db)
        chip = _make_chip(db, res, "party_info")
        chip.send_status = "failed"
        chip.send_error = "boom"

        result = exclude_chip(db, reservation_id=res.id, template_key="party_info", date=today_kst())

        assert result is chip
        assert chip.assigned_by == "excluded"
        assert chip.sent_at is None
        assert chip.send_status is None
        assert chip.send_error is None

    def test_exclude_missing_chip_returns_none(self, db):
        res = _make_reservation(db)
        assert exclude_chip(db, reservation_id=res.id, template_key="nope", date=today_kst()) is None

    def test_reassign_restores_excluded_chip(self, db):
        """체크해제 → 재체크 = 처음 체크한 것과 같은 상태 (manual). 409 아님."""
        res = _make_reservation(db)
        chip = _make_chip(db, res, "party_info")
        exclude_chip(db, reservation_id=res.id, template_key="party_info", date=today_kst())

        result = assign_manual_chip(db, reservation_id=res.id, template_key="party_info", date=today_kst())

        assert result is chip
        assert chip.assigned_by == "manual"

    def test_assign_creates_new_chip(self, db):
        res = _make_reservation(db)
        chip = assign_manual_chip(db, reservation_id=res.id, template_key="party_info", date=today_kst())
        assert chip is not None
        assert chip.assigned_by == "manual"

    def test_assign_active_chip_is_duplicate(self, db):
        """이미 활성 칩이면 None — 엔드포인트가 409 처리. 상태는 건드리지 않음."""
        res = _make_reservation(db)
        chip = _make_chip(db, res, "party_info", assigned_by="auto")

        assert assign_manual_chip(db, reservation_id=res.id, template_key="party_info", date=today_kst()) is None
        assert chip.assigned_by == "auto"


# ════════════════════════════════════════════════════════════════════
# 발송 경로 차단
# ════════════════════════════════════════════════════════════════════

class TestStandardScheduleSkipsExcluded:
    def test_excluded_reservation_not_targeted(self, db):
        """exclude_sent=False 스케줄에서도 차단 — 옵션과 무관한 규칙."""
        tpl = _make_template(db)
        sched = _make_schedule(db, tpl, target_mode="first_night", date_target="today", exclude_sent=False)
        excluded_res = _make_reservation(db)
        normal_res = _make_reservation(db)
        _make_chip(db, excluded_res, "party_info", assigned_by="excluded")

        ids = [r.id for r in _executor(db)._get_targets_standard(sched)]

        assert excluded_res.id not in ids
        assert normal_res.id in ids

    def test_excluded_on_other_date_does_not_block(self, db):
        """칩은 (예약, 템플릿, 날짜) 단위 — 다른 날짜를 끈 것은 오늘 발송에 영향 없음."""
        tpl = _make_template(db)
        sched = _make_schedule(db, tpl, target_mode="first_night", date_target="today", exclude_sent=False)
        res = _make_reservation(db)
        other = (date.fromisoformat(today_kst()) + timedelta(days=1)).isoformat()
        _make_chip(db, res, "party_info", date_str=other, assigned_by="excluded")

        ids = [r.id for r in _executor(db)._get_targets_standard(sched)]
        assert res.id in ids

    def test_restored_chip_targeted_again(self, db):
        tpl = _make_template(db)
        sched = _make_schedule(db, tpl, target_mode="first_night", date_target="today", exclude_sent=False)
        res = _make_reservation(db)
        _make_chip(db, res, "party_info")
        exclude_chip(db, reservation_id=res.id, template_key="party_info", date=today_kst())
        assign_manual_chip(db, reservation_id=res.id, template_key="party_info", date=today_kst())

        ids = [r.id for r in _executor(db)._get_targets_standard(sched)]
        assert res.id in ids


class TestCustomScheduleSkipsExcluded:
    def test_excluded_chip_not_targeted(self, db):
        tpl = _make_template(db, key="add_one_person")
        sched = _make_schedule(
            db, tpl, schedule_category="custom_schedule", custom_type="surcharge_1",
        )
        res = _make_reservation(db)
        _make_chip(db, res, "add_one_person", assigned_by="excluded", schedule_id=sched.id)

        assert _executor(db).get_targets(sched) == []


class TestEventScheduleSkipsExcluded:
    def test_excluded_chip_not_targeted(self, db):
        tpl = _make_template(db, key="welcome")
        sched = _make_schedule(db, tpl, schedule_category="event", schedule_type="hourly", hour=None)
        future = (date.fromisoformat(today_kst()) + timedelta(days=3)).isoformat()
        excluded_res = _make_reservation(db, check_in=future)
        normal_res = _make_reservation(db, check_in=future)
        _make_chip(db, excluded_res, "welcome", date_str=future, assigned_by="excluded")

        ids = [r.id for r in _executor(db)._get_targets_event(sched)]

        assert excluded_res.id not in ids
        assert normal_res.id in ids


class TestSendByAssignmentSkipsExcluded:
    def test_only_non_excluded_chips_sent(self, db):
        """일괄발송 — excluded 만 제외. assigned_by NULL(레거시) 칩은 그대로 발송."""
        _make_template(db)
        auto_res = _make_reservation(db, phone="01011111111")
        null_res = _make_reservation(db, phone="01022222222")
        excluded_res = _make_reservation(db, phone="01033333333")
        _make_chip(db, auto_res, "party_info", assigned_by="auto")
        _make_chip(db, null_res, "party_info", assigned_by=None)
        _make_chip(db, excluded_res, "party_info", assigned_by="excluded")

        provider = MockSMSProvider()
        # asyncio.run() 은 종료 시 전역 루프를 비워 get_event_loop() 쓰는 다른 테스트를 깨뜨림 — 독립 루프 사용
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                SmsSender(db, provider).send_by_assignment(template_key="party_info", date=today_kst())
            )
        finally:
            loop.close()

        assert result["target_count"] == 2
        assert sorted(provider.calls) == ["01011111111", "01022222222"]
