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
