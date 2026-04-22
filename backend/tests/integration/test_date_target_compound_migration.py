"""C-1/C-2 회귀 방지: today_checkout → yesterday+last_day 마이그레이션 시뮬레이션.

시나리오:
  1. 예약 생성 (check_out=오늘)
  2. 과거 today_checkout 스케줄로 발송된 칩 (date=check_out_date) 존재
  3. 마이그레이션: schedule.date_target='yesterday', target_mode='last_night' 로 UPDATE
                   칩의 date = check_out_date - 1 (last_day shift)
  4. 변환 후 get_targets() 호출 → 동일 예약자가 재발송 대상에 포함되지 않아야 함
     (exclude_sent 가 shifted date 로 매칭돼야 함)
"""
import json
from datetime import datetime, timezone, timedelta

import pytest

from app.config import today_kst, today_kst_date
from app.db.models import (
    MessageTemplate,
    Reservation,
    ReservationSmsAssignment,
    ReservationStatus,
    TemplateSchedule,
)
from app.scheduler.template_scheduler import TemplateScheduleExecutor


def _executor(db):
    return TemplateScheduleExecutor(db, tenant=None)


def _make_template(db, key="checkout_guide"):
    tpl = MessageTemplate(
        tenant_id=1, template_key=key, name="퇴실안내",
        content="퇴실 안내입니다.", is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _make_schedule(db, tpl, *, date_target, target_mode, exclude_sent=True):
    sched = TemplateSchedule(
        tenant_id=1,
        template_id=tpl.id,
        schedule_name="퇴실안내 발송",
        schedule_type="daily",
        hour=9,
        minute=0,
        date_target=date_target,
        target_mode=target_mode,
        exclude_sent=exclude_sent,
        is_active=True,
    )
    db.add(sched)
    db.flush()
    return sched


def _make_reservation(db, *, check_in, check_out):
    res = Reservation(
        tenant_id=1,
        customer_name="마이그레이션손님",
        phone="01099998888",
        check_in_date=check_in,
        check_in_time="15:00",
        check_out_date=check_out,
        status=ReservationStatus.CONFIRMED,
    )
    db.add(res)
    db.flush()
    return res


def _make_sent_chip(db, reservation, tpl, sched, *, date):
    chip = ReservationSmsAssignment(
        tenant_id=1,
        reservation_id=reservation.id,
        template_key=tpl.template_key,
        date=date,
        assigned_by="schedule",
        schedule_id=sched.id,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(chip)
    db.flush()
    return chip


class TestDateTargetCompoundMigration:
    def test_migrated_schedule_no_resend_after_chip_date_shift(self, db):
        """마이그레이션 후 exclude_sent 가 shifted chip date 로 올바르게 매칭 — 재발송 없음."""
        today = today_kst_date()
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        checkin = (today - timedelta(days=2)).strftime("%Y-%m-%d")

        tpl = _make_template(db)

        # 마이그레이션 완료 스케줄: yesterday + last_day
        sched = _make_schedule(db, tpl, date_target="yesterday", target_mode="last_night",
                               exclude_sent=True)

        # 예약: check_out=오늘 → last_day=어제
        res = _make_reservation(db, check_in=checkin, check_out=today_str)

        # 마이그레이션된 칩: date 가 check_out-1=어제 로 shift 된 상태
        _make_sent_chip(db, res, tpl, sched, date=yesterday)

        executor = _executor(db)
        targets = executor._get_targets_standard(sched)

        ids = [t.id for t in targets]
        assert res.id not in ids, (
            "이미 발송된 예약이 마이그레이션 후에도 재발송 대상에 포함되면 안 됨"
        )

    def test_migrated_schedule_sends_to_unreceived_reservation(self, db):
        """칩이 없는 예약은 마이그레이션 후에도 정상 발송 대상."""
        today = today_kst_date()
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        checkin = (today - timedelta(days=2)).strftime("%Y-%m-%d")

        tpl = _make_template(db, key="checkout_guide_2")

        sched = _make_schedule(db, tpl, date_target="yesterday", target_mode="last_night",
                               exclude_sent=True)

        # 미발송 예약 (칩 없음)
        res = _make_reservation(db, check_in=checkin, check_out=today_str)

        executor = _executor(db)
        targets = executor._get_targets_standard(sched)

        assert res.id in [t.id for t in targets], (
            "칩이 없는 예약은 last_day+yesterday 스케줄에서 발송 대상이어야 함"
        )

    def test_migrated_schedule_different_checkout_not_included(self, db):
        """check_out이 내일인 예약은 last_day=오늘 → yesterday target 과 불일치, 제외."""
        today = today_kst_date()
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")

        tpl = _make_template(db, key="checkout_guide_3")
        sched = _make_schedule(db, tpl, date_target="yesterday", target_mode="last_night",
                               exclude_sent=True)

        # check_out=내일 → last_day=오늘 ≠ yesterday
        res = _make_reservation(db, check_in=yesterday, check_out=tomorrow)

        executor = _executor(db)
        targets = executor._get_targets_standard(sched)

        assert res.id not in [t.id for t in targets], (
            "last_day=오늘인 예약은 date_target=yesterday 스케줄에서 제외돼야 함"
        )
