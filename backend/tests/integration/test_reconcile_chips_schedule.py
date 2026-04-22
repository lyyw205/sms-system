"""reconcile_chips_for_schedule() 통합 테스트 — in-memory SQLite."""
import json
import pytest
from datetime import datetime, timezone
from app.db.models import (
    Reservation, Room, Building, RoomAssignment,
    ReservationStatus, TemplateSchedule, MessageTemplate,
    ReservationSmsAssignment,
)
from app.services.chip_reconciler import reconcile_chips_for_schedule
from app.config import today_kst


def _make_template(db, key="tpl_test"):
    tpl = MessageTemplate(
        tenant_id=1, template_key=key, name="Test", content="hello", is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _make_schedule(db, template, is_active=True, target_mode='first_night', date_target='today'):
    sched = TemplateSchedule(
        tenant_id=1, template_id=template.id, schedule_name="test",
        schedule_type="daily", hour=9, minute=0,
        is_active=is_active,
        target_mode=target_mode,
        date_target=date_target,
    )
    db.add(sched)
    db.flush()
    return sched


def _make_reservation(db, check_in=None, status=ReservationStatus.CONFIRMED):
    check_in = check_in or today_kst()
    res = Reservation(
        tenant_id=1, customer_name="손님", phone="01012345678",
        check_in_date=check_in, check_in_time="15:00",
        status=status,
    )
    db.add(res)
    db.flush()
    return res


class TestReconcileChipsForSchedule:
    def test_active_schedule_creates_chips(self, db):
        """활성 스케줄 + 매칭 예약 → 칩 생성."""
        tpl = _make_template(db)
        sched = _make_schedule(db, tpl, is_active=True)
        res = _make_reservation(db, check_in=today_kst())

        created = reconcile_chips_for_schedule(db, sched)
        db.flush()

        assert created >= 1
        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.template_key == tpl.template_key,
        ).all()
        assert len(chips) >= 1

    def test_inactive_schedule_deletes_chips(self, db):
        """비활성 스케줄 → 기존 칩 삭제."""
        tpl = _make_template(db, key="tpl_inactive")
        sched = _make_schedule(db, tpl, is_active=False)
        res = _make_reservation(db)

        # Pre-create a chip owned by this schedule
        chip = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res.id,
            template_key=tpl.template_key,
            date=today_kst(),
            assigned_by='schedule',
            schedule_id=sched.id,
        )
        db.add(chip)
        db.flush()

        reconcile_chips_for_schedule(db, sched)
        db.flush()

        remaining = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.template_key == tpl.template_key,
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()
        assert len(remaining) == 0

    def test_sent_chip_preserved(self, db):
        """sent_at 있는 칩(발송 완료)은 보호 — 삭제 안 됨."""
        tpl = _make_template(db, key="tpl_sent")
        sched = _make_schedule(db, tpl, is_active=False)
        res = _make_reservation(db)

        chip = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res.id,
            template_key=tpl.template_key,
            date=today_kst(),
            assigned_by='schedule',
            schedule_id=sched.id,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(chip)
        db.flush()

        reconcile_chips_for_schedule(db, sched)
        db.flush()

        remaining = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.template_key == tpl.template_key,
        ).all()
        # sent chip preserved
        assert len(remaining) == 1
        assert remaining[0].sent_at is not None

    def test_manual_chip_preserved(self, db):
        """assigned_by='manual' 칩은 보호 — 삭제 안 됨."""
        tpl = _make_template(db, key="tpl_manual")
        sched = _make_schedule(db, tpl, is_active=False)
        res = _make_reservation(db)

        chip = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res.id,
            template_key=tpl.template_key,
            date=today_kst(),
            assigned_by='manual',
            schedule_id=sched.id,
        )
        db.add(chip)
        db.flush()

        reconcile_chips_for_schedule(db, sched)
        db.flush()

        remaining = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.template_key == tpl.template_key,
        ).all()
        assert len(remaining) == 1
        assert remaining[0].assigned_by == 'manual'


from app.services.chip_reconciler import reconcile_chips_for_reservation  # noqa: E402


class TestCustomScheduleExclusion:
    def test_standard_reconcile_does_not_delete_custom_chips(self, db):
        """chip_reconciler가 custom_schedule 소속 칩을 삭제하지 않는다."""
        tpl = _make_template(db, key="tpl_custom")
        # custom_schedule 타입 스케줄 생성
        custom_sched = TemplateSchedule(
            tenant_id=1, template_id=tpl.id, schedule_name="custom test",
            schedule_type="daily", hour=13, minute=0,
            schedule_category="custom_schedule",
            custom_type="surcharge_1", is_active=True,
        )
        db.add(custom_sched)
        db.flush()

        res = _make_reservation(db, check_in=today_kst())

        # custom_schedule 소속 칩 생성 (assigned_by='auto')
        chip = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res.id,
            template_key=tpl.template_key,
            date=today_kst(),
            assigned_by='auto',
            schedule_id=custom_sched.id,
        )
        db.add(chip)
        db.flush()

        # standard reconcile 실행
        reconcile_chips_for_reservation(db, res.id)
        db.flush()

        remaining = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.schedule_id == custom_sched.id,
        ).all()
        assert len(remaining) == 1, "custom_schedule 칩은 standard reconcile에서 삭제되면 안 됨"


class TestNonCandidateChipPreservation:
    """reconcile_chips_for_schedule 은 candidate 범위 밖 예약의 칩을 건드리면 안 됨.

    회귀 방지: 과거 버그에서는 scope_dates 에 우연히 포함된 타 예약의 칩까지
    existing 으로 잡혀 `expected_pairs` 에 없다는 이유로 삭제됐다.
    (2026-04-22 운영 중 스케줄 저장 시 테스트 예약 칩 10개가 연쇄 삭제된 사건)
    """

    def test_non_candidate_chip_not_deleted(self, db):
        """candidate 밖 예약의 칩은 scope_dates 겹쳐도 삭제되면 안 됨."""
        from datetime import timedelta
        from app.config import today_kst_date

        tpl = _make_template(db, key="tpl_overlap")
        # date_target=yesterday + target_mode=last_night → target_date=today-1
        sched = _make_schedule(db, tpl, target_mode='last_night', date_target='yesterday')

        today = today_kst_date()
        ystd = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        tmrw = (today + timedelta(days=1)).strftime('%Y-%m-%d')

        # Candidate A: target_date(ystd) stay-coverage PASS
        # check_in=ystd-2, check_out=tmrw+1 (2박) → last_night=tmrw (scope_dates 에 tmrw 추가됨)
        res_a = Reservation(
            tenant_id=1, customer_name="A", phone="01011112222",
            check_in_date=(today - timedelta(days=2)).strftime('%Y-%m-%d'),
            check_out_date=(today + timedelta(days=2)).strftime('%Y-%m-%d'),
            check_in_time="15:00",
            status=ReservationStatus.CONFIRMED,
        )
        db.add(res_a)
        db.flush()

        # Innocent B: tmrw 체크인 — target_date=ystd stay-coverage FAIL → candidate 아님
        # 하지만 date=tmrw 인 칩이 이미 있음 (다른 경로로 생성된 정상 칩)
        res_b = Reservation(
            tenant_id=1, customer_name="B", phone="01033334444",
            check_in_date=tmrw,
            check_out_date=None,
            check_in_time="15:00",
            status=ReservationStatus.CONFIRMED,
        )
        db.add(res_b)
        db.flush()

        # B 의 tmrw 칩 pre-seed (reservation-centric reconcile 로 생성됐다고 가정)
        innocent_chip = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res_b.id,
            template_key=tpl.template_key,
            date=tmrw,
            assigned_by='auto',
            schedule_id=sched.id,
        )
        db.add(innocent_chip)
        db.flush()

        # schedule-centric reconcile 실행 (스케줄 저장 시 발화)
        reconcile_chips_for_schedule(db, sched)
        db.flush()

        # B 의 칩이 살아있어야 함 (버그 시 삭제됨)
        survivors = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res_b.id,
            ReservationSmsAssignment.schedule_id == sched.id,
            ReservationSmsAssignment.date == tmrw,
        ).all()
        assert len(survivors) == 1, (
            "candidate 범위 밖 예약의 칩이 scope_dates 겹침만으로 삭제되면 안 됨"
        )
