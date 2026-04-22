"""first_night + stay_group dedup 통합 테스트.

수동 연결된 stay_group 내에서 target_mode='first_night' 스케줄이
그룹의 첫 멤버(stay_group_order=0)에만 칩을 생성하는지 검증.
"""
import pytest
from datetime import timedelta
from app.db.models import (
    Reservation, ReservationStatus, MessageTemplate, TemplateSchedule,
    ReservationSmsAssignment,
)
from app.services.chip_reconciler import reconcile_chips_for_schedule
from app.config import today_kst, today_kst_date


def _make_template(db, key="first_night_grp_tpl"):
    tpl = MessageTemplate(
        tenant_id=1, template_key=key, name="Test", content="hello", is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _make_schedule(db, template):
    sched = TemplateSchedule(
        tenant_id=1, template_id=template.id, schedule_name="first_night_grp_test",
        schedule_type="daily", hour=9, minute=0,
        target_mode='first_night',
        date_target='today',
        is_active=True,
    )
    db.add(sched)
    db.flush()
    return sched


class TestFirstNightGroupDedup:
    def test_only_first_member_gets_chip(self, db):
        """stay_group 내 첫 멤버(order=0)에만 칩 생성, 두 번째 멤버(order=1)는 건너뜀."""
        tpl = _make_template(db)
        sched = _make_schedule(db, tpl)

        today = today_kst()
        tomorrow = (today_kst_date() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (today_kst_date() + timedelta(days=2)).strftime("%Y-%m-%d")
        group_id = "manual-test-group-001"

        # A: 첫 번째 예약 (order=0) — 체크인 오늘, 내일 체크아웃 (연박 1박)
        # check_out > today 이어야 stay-coverage 필터를 통과함
        res_a = Reservation(
            tenant_id=1, customer_name="김철수", phone="01011111111",
            check_in_date=today, check_in_time="15:00",
            check_out_date=tomorrow,
            status=ReservationStatus.CONFIRMED,
            is_long_stay=True,
            stay_group_id=group_id,
            stay_group_order=0,
            is_last_in_group=False,
        )
        db.add(res_a)
        db.flush()

        # B: 두 번째 예약 (order=1) — 내일 체크인, 모레 체크아웃 (그룹 마지막 멤버)
        res_b = Reservation(
            tenant_id=1, customer_name="김철수", phone="01011111111",
            check_in_date=tomorrow, check_in_time="15:00",
            check_out_date=day_after,
            status=ReservationStatus.CONFIRMED,
            is_long_stay=True,
            stay_group_id=group_id,
            stay_group_order=1,
            is_last_in_group=True,
        )
        db.add(res_b)
        db.flush()

        reconcile_chips_for_schedule(db, sched)
        db.flush()

        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()

        chip_res_ids = {c.reservation_id for c in chips}

        assert res_a.id in chip_res_ids, "첫 멤버(order=0)에 칩이 있어야 함"
        assert res_b.id not in chip_res_ids, "두 번째 멤버(order=1)에는 칩이 없어야 함"
        assert len(chips) == 1, f"칩은 정확히 1개여야 함, 실제: {len(chips)}"

    def test_standalone_reservation_gets_chip(self, db):
        """stay_group 없는 단일 예약은 first_night 에 칩 생성됨."""
        tpl = _make_template(db, key="first_night_standalone_tpl")
        sched = _make_schedule(db, tpl)

        today = today_kst()
        res = Reservation(
            tenant_id=1, customer_name="이영희", phone="01022222222",
            check_in_date=today, check_in_time="15:00",
            status=ReservationStatus.CONFIRMED,
            is_long_stay=False,
            stay_group_id=None,
        )
        db.add(res)
        db.flush()

        reconcile_chips_for_schedule(db, sched)
        db.flush()

        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.schedule_id == sched.id,
            ReservationSmsAssignment.reservation_id == res.id,
        ).all()

        assert len(chips) == 1, "단일 예약은 칩 1개 생성돼야 함"
