"""surcharge.py 통합 테스트 — in-memory SQLite."""
import pytest
from datetime import datetime, timezone

from app.db.models import (
    Reservation, Room, Building, RoomAssignment,
    ReservationStatus, TemplateSchedule, MessageTemplate,
    ReservationSmsAssignment,
)
from app.services.surcharge import reconcile_surcharge, reconcile_surcharge_batch


DATE = "2026-04-15"


def _make_building(db, name="본관"):
    b = Building(tenant_id=1, name=name, is_active=True)
    db.add(b)
    db.flush()
    return b


def _make_room(db, building_id, room_number="R101", base_capacity=2, is_dormitory=False):
    r = Room(
        tenant_id=1, room_number=room_number, room_type="더블",
        building_id=building_id, is_active=True,
        is_dormitory=is_dormitory, base_capacity=base_capacity,
    )
    db.add(r)
    db.flush()
    return r


def _make_reservation(db, check_in=DATE, check_out="2026-04-16",
                       party_size=None, male_count=None, female_count=None):
    res = Reservation(
        tenant_id=1, customer_name="테스트", phone="01012345678",
        check_in_date=check_in, check_in_time="15:00",
        check_out_date=check_out,
        status=ReservationStatus.CONFIRMED,
        party_size=party_size,
        male_count=male_count,
        female_count=female_count,
    )
    db.add(res)
    db.flush()
    return res


def _make_assignment(db, reservation_id, room_id, date=DATE):
    ra = RoomAssignment(
        tenant_id=1, reservation_id=reservation_id,
        room_id=room_id, date=date, assigned_by="auto",
    )
    db.add(ra)
    db.flush()
    return ra


def _make_template(db, key="add_one_person", name="1인추가"):
    t = MessageTemplate(
        tenant_id=1, template_key=key, name=name,
        content="추가요금 안내", is_active=True,
    )
    db.add(t)
    db.flush()
    return t


def _make_surcharge_schedule(db, template, custom_type="surcharge_1"):
    s = TemplateSchedule(
        tenant_id=1, template_id=template.id,
        schedule_name=f"테스트 {custom_type}",
        schedule_type="daily", hour=13, minute=30,
        schedule_category="custom_schedule",
        custom_type=custom_type, is_active=True,
    )
    db.add(s)
    db.flush()
    return s


def _surcharge_chips(db, reservation_id, date=DATE):
    """예약-날짜에 대한 surcharge 칩 목록을 반환합니다."""
    surcharge_schedule_ids = [
        s.id for s in db.query(TemplateSchedule).filter(
            TemplateSchedule.schedule_category == "custom_schedule",
            TemplateSchedule.custom_type.like("surcharge_%"),
        ).all()
    ]
    if not surcharge_schedule_ids:
        return []
    return db.query(ReservationSmsAssignment).filter(
        ReservationSmsAssignment.reservation_id == reservation_id,
        ReservationSmsAssignment.date == date,
        ReservationSmsAssignment.schedule_id.in_(surcharge_schedule_ids),
    ).all()


class TestReconcileSurcharge:
    def test_creates_chip_when_excess_matches(self, db):
        """base_capacity=2, party_size=3 → excess=1 → surcharge_1 칩 생성."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=3)
        _make_assignment(db, res.id, room.id)

        tpl = _make_template(db, key="add_one_person")
        schedule = _make_surcharge_schedule(db, tpl, custom_type="surcharge_1")

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        assert len(chips) == 1
        assert chips[0].schedule_id == schedule.id
        assert chips[0].assigned_by == "auto"

    def test_deletes_stale_chip_when_excess_changes(self, db):
        """초과 인원이 1→2로 바뀌면 surcharge_1 칩 삭제 + surcharge_2 칩 생성."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=4)  # excess=2

        tpl1 = _make_template(db, key="add_one_person", name="1인추가")
        s1 = _make_surcharge_schedule(db, tpl1, custom_type="surcharge_1")

        tpl2 = _make_template(db, key="add_two_person", name="2인추가")
        s2 = _make_surcharge_schedule(db, tpl2, custom_type="surcharge_2")

        _make_assignment(db, res.id, room.id)

        # Pre-insert stale surcharge_1 chip (excess was 1 before)
        stale = ReservationSmsAssignment(
            tenant_id=1, reservation_id=res.id,
            template_key=tpl1.template_key, date=DATE,
            assigned_by="auto", schedule_id=s1.id, sent_at=None,
        )
        db.add(stale)
        db.flush()

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        schedule_ids = {c.schedule_id for c in chips}
        assert s1.id not in schedule_ids, "surcharge_1 chip should be deleted"
        assert s2.id in schedule_ids, "surcharge_2 chip should be created"

    def test_no_chip_when_no_excess(self, db):
        """party_size == base_capacity → excess=0 → 모든 surcharge 칩 삭제."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=2)

        tpl = _make_template(db, key="add_one_person")
        s = _make_surcharge_schedule(db, tpl, custom_type="surcharge_1")

        _make_assignment(db, res.id, room.id)

        # Pre-insert a stale surcharge_1 chip
        stale = ReservationSmsAssignment(
            tenant_id=1, reservation_id=res.id,
            template_key=tpl.template_key, date=DATE,
            assigned_by="auto", schedule_id=s.id, sent_at=None,
        )
        db.add(stale)
        db.flush()

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        assert len(chips) == 0

    def test_skips_dormitory(self, db):
        """도미토리 객실은 surcharge 칩 생성 안 함."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2, is_dormitory=True)
        res = _make_reservation(db, party_size=5)

        tpl = _make_template(db, key="add_one_person")
        _make_surcharge_schedule(db, tpl, custom_type="surcharge_1")

        _make_assignment(db, res.id, room.id)

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        assert len(chips) == 0

    def test_deletes_all_when_no_assignment(self, db):
        """RoomAssignment 없으면 기존 surcharge 칩 전부 삭제."""
        res = _make_reservation(db, party_size=3)

        tpl = _make_template(db, key="add_one_person")
        s = _make_surcharge_schedule(db, tpl, custom_type="surcharge_1")

        # Pre-insert chip (no room assignment)
        stale = ReservationSmsAssignment(
            tenant_id=1, reservation_id=res.id,
            template_key=tpl.template_key, date=DATE,
            assigned_by="auto", schedule_id=s.id, sent_at=None,
        )
        db.add(stale)
        db.flush()

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        assert len(chips) == 0

    def test_preserves_sent_chip(self, db):
        """sent_at 있는 칩은 보존 — 삭제 안 됨."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=4)  # excess=2

        tpl1 = _make_template(db, key="add_one_person", name="1인추가")
        s1 = _make_surcharge_schedule(db, tpl1, custom_type="surcharge_1")

        tpl2 = _make_template(db, key="add_two_person", name="2인추가")
        s2 = _make_surcharge_schedule(db, tpl2, custom_type="surcharge_2")

        _make_assignment(db, res.id, room.id)

        # Pre-insert surcharge_1 chip that was already sent
        sent_chip = ReservationSmsAssignment(
            tenant_id=1, reservation_id=res.id,
            template_key=tpl1.template_key, date=DATE,
            assigned_by="auto", schedule_id=s1.id,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(sent_chip)
        db.flush()

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        schedule_ids = {c.schedule_id for c in chips}
        assert s1.id in schedule_ids, "sent surcharge_1 chip should be preserved"
        assert s2.id in schedule_ids, "surcharge_2 chip should be created"

    def test_no_chip_when_schedule_missing(self, db):
        """surcharge_1 스케줄이 없으면 칩 생성 안 함 — 예외도 없음."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=3)  # excess=1

        _make_assignment(db, res.id, room.id)
        # No surcharge schedule created

        reconcile_surcharge(db, res.id, DATE)  # should not raise

        chips = _surcharge_chips(db, res.id)
        assert len(chips) == 0

    def test_batch_handles_multiple_reservations(self, db):
        """reconcile_surcharge_batch: 초과 예약만 칩 생성, 정원 내 예약은 칩 없음."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)

        # res1: party_size=3 (excess=1) → chip expected
        res1 = _make_reservation(db, party_size=3)
        _make_assignment(db, res1.id, room.id)

        # res2: party_size=2 (no excess) → no chip
        res2 = _make_reservation(db, party_size=2)
        _make_assignment(db, res2.id, room.id)

        tpl = _make_template(db, key="add_one_person")
        _make_surcharge_schedule(db, tpl, custom_type="surcharge_1")

        reconcile_surcharge_batch(db, [res1.id, res2.id], DATE)

        chips1 = _surcharge_chips(db, res1.id)
        chips2 = _surcharge_chips(db, res2.id)
        assert len(chips1) == 1, "초과 예약에 칩이 생성되어야 함"
        assert len(chips2) == 0, "정원 내 예약에 칩이 없어야 함"
