"""surcharge.py 통합 테스트 — in-memory SQLite (2-type 재설계 기준).

2-type 구조:
  - surcharge_standard: 일반 객실 인원 초과
  - surcharge_double:   더블룸 인원 초과 (DOUBLE_ROOM_BIZ_ITEM_IDS 기반)
"""
import pytest
from datetime import datetime, timezone

from app.db.models import (
    Reservation, Room, Building, RoomAssignment,
    ReservationStatus, TemplateSchedule, MessageTemplate,
    ReservationSmsAssignment, RoomBizItemLink,
)
from app.services.surcharge import (
    reconcile_surcharge, reconcile_surcharge_batch,
    SURCHARGE_STANDARD, SURCHARGE_DOUBLE, DOUBLE_ROOM_BIZ_ITEM_IDS,
)


DATE = "2026-04-15"
DOUBLE_BIZ_ID = next(iter(DOUBLE_ROOM_BIZ_ITEM_IDS))


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

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


def _link_double_biz_item(db, room_id, biz_item_id=DOUBLE_BIZ_ID):
    """방을 더블룸으로 표시하는 RoomBizItemLink 생성."""
    link = RoomBizItemLink(
        tenant_id=1,
        room_id=room_id,
        biz_item_id=biz_item_id,
    )
    db.add(link)
    db.flush()
    return link


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
        notes='테스트',  # [테스트 마커] surcharge 발송 대상 조건
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


def _make_template(db, key="add_standard", name="일반추가요금"):
    t = MessageTemplate(
        tenant_id=1, template_key=key, name=name,
        content="추가요금 안내", is_active=True,
    )
    db.add(t)
    db.flush()
    return t


def _make_surcharge_schedule(db, template, custom_type=SURCHARGE_STANDARD):
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReconcileSurcharge:
    def test_standard_room_excess_creates_standard_chip(self, db):
        """일반 객실, 2인 초과 → surcharge_standard 칩 생성, surcharge_double 칩 없음."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=3)
        _make_assignment(db, res.id, room.id)

        tpl = _make_template(db, key="add_standard", name="일반추가요금")
        schedule_std = _make_surcharge_schedule(db, tpl, custom_type=SURCHARGE_STANDARD)
        tpl_dbl = _make_template(db, key="add_double", name="더블추가요금")
        schedule_dbl = _make_surcharge_schedule(db, tpl_dbl, custom_type=SURCHARGE_DOUBLE)

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        schedule_ids = {c.schedule_id for c in chips}
        assert schedule_std.id in schedule_ids, "surcharge_standard 칩이 생성되어야 함"
        assert schedule_dbl.id not in schedule_ids, "surcharge_double 칩이 없어야 함"

    def test_double_room_excess_creates_double_chip(self, db):
        """더블룸 (biz_item_id=DOUBLE_BIZ_ID), 1인 초과 → surcharge_double 칩 생성, surcharge_standard 칩 없음."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        _link_double_biz_item(db, room.id)
        res = _make_reservation(db, party_size=3)
        _make_assignment(db, res.id, room.id)

        tpl_std = _make_template(db, key="add_standard", name="일반추가요금")
        schedule_std = _make_surcharge_schedule(db, tpl_std, custom_type=SURCHARGE_STANDARD)
        tpl_dbl = _make_template(db, key="add_double", name="더블추가요금")
        schedule_dbl = _make_surcharge_schedule(db, tpl_dbl, custom_type=SURCHARGE_DOUBLE)

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        schedule_ids = {c.schedule_id for c in chips}
        assert schedule_dbl.id in schedule_ids, "surcharge_double 칩이 생성되어야 함"
        assert schedule_std.id not in schedule_ids, "surcharge_standard 칩이 없어야 함"

    def test_no_chip_when_no_excess(self, db):
        """일반 객실, party_size == base_capacity → excess=0 → 칩 없음."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=2)

        tpl = _make_template(db, key="add_standard")
        s = _make_surcharge_schedule(db, tpl, custom_type=SURCHARGE_STANDARD)

        _make_assignment(db, res.id, room.id)

        # Pre-insert a stale chip to verify it gets cleaned up
        stale = ReservationSmsAssignment(
            tenant_id=1, reservation_id=res.id,
            template_key=tpl.template_key, date=DATE,
            assigned_by="auto", schedule_id=s.id, sent_at=None,
        )
        db.add(stale)
        db.flush()

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        assert len(chips) == 0, "excess=0 이므로 칩이 없어야 함"

    def test_dormitory_creates_no_chip(self, db):
        """도미토리 객실은 surcharge 칩 생성 안 함."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2, is_dormitory=True)
        res = _make_reservation(db, party_size=5)

        tpl = _make_template(db, key="add_standard")
        _make_surcharge_schedule(db, tpl, custom_type=SURCHARGE_STANDARD)

        _make_assignment(db, res.id, room.id)

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        assert len(chips) == 0, "도미토리는 칩 없어야 함"

    def test_deletes_all_when_no_assignment(self, db):
        """RoomAssignment 없으면 기존 surcharge 칩 전부 삭제."""
        res = _make_reservation(db, party_size=3)

        tpl = _make_template(db, key="add_standard")
        s = _make_surcharge_schedule(db, tpl, custom_type=SURCHARGE_STANDARD)

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
        assert len(chips) == 0, "배정 없으면 기존 칩도 삭제되어야 함"

    def test_type_switch_standard_to_double(self, db):
        """일반 → 더블룸으로 이동 후 reconcile → standard 칩 삭제, double 칩 생성."""
        b = _make_building(db)
        # Double room
        room = _make_room(db, b.id, base_capacity=2)
        _link_double_biz_item(db, room.id)

        res = _make_reservation(db, party_size=3)
        _make_assignment(db, res.id, room.id)

        tpl_std = _make_template(db, key="add_standard", name="일반추가요금")
        s_std = _make_surcharge_schedule(db, tpl_std, custom_type=SURCHARGE_STANDARD)
        tpl_dbl = _make_template(db, key="add_double", name="더블추가요금")
        s_dbl = _make_surcharge_schedule(db, tpl_dbl, custom_type=SURCHARGE_DOUBLE)

        # Stale standard chip from when it was a regular room
        stale = ReservationSmsAssignment(
            tenant_id=1, reservation_id=res.id,
            template_key=tpl_std.template_key, date=DATE,
            assigned_by="auto", schedule_id=s_std.id, sent_at=None,
        )
        db.add(stale)
        db.flush()

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        schedule_ids = {c.schedule_id for c in chips}
        assert s_std.id not in schedule_ids, "standard 칩이 삭제되어야 함 (타입 전환)"
        assert s_dbl.id in schedule_ids, "double 칩이 생성되어야 함"

    def test_batch_handles_multiple_reservations_individually(self, db):
        """reconcile_surcharge_batch: 초과 예약만 칩 생성, 정원 내 예약은 칩 없음."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)

        # res1: party_size=3 (excess=1) → chip expected
        res1 = _make_reservation(db, party_size=3)
        _make_assignment(db, res1.id, room.id)

        # res2: party_size=2 (no excess) → no chip
        res2 = _make_reservation(db, party_size=2)
        _make_assignment(db, res2.id, room.id)

        tpl = _make_template(db, key="add_standard")
        _make_surcharge_schedule(db, tpl, custom_type=SURCHARGE_STANDARD)

        reconcile_surcharge_batch(db, [res1.id, res2.id], DATE)

        chips1 = _surcharge_chips(db, res1.id)
        chips2 = _surcharge_chips(db, res2.id)
        assert len(chips1) == 1, "초과 예약에 칩이 생성되어야 함"
        assert len(chips2) == 0, "정원 내 예약에 칩이 없어야 함"

    def test_batch_continues_on_individual_failure(self, db, monkeypatch):
        """배치 reconcile — 한 건 예외가 나머지 처리를 막지 않음."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)

        res1 = _make_reservation(db, party_size=3)
        _make_assignment(db, res1.id, room.id)
        res2 = _make_reservation(db, party_size=3)
        _make_assignment(db, res2.id, room.id)

        tpl = _make_template(db, key="add_standard")
        _make_surcharge_schedule(db, tpl, custom_type=SURCHARGE_STANDARD)

        call_count = {"n": 0}
        original = reconcile_surcharge

        def _failing_once(db_arg, rid, date_arg, room_id=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("첫 번째 실패 시뮬레이션")
            original(db_arg, rid, date_arg, room_id=room_id)

        import app.services.surcharge as surcharge_mod
        monkeypatch.setattr(surcharge_mod, "reconcile_surcharge", _failing_once)

        # Should not raise even though first call fails
        reconcile_surcharge_batch(db, [res1.id, res2.id], DATE)

        # Only res2 was processed successfully (res1 failed)
        chips2 = _surcharge_chips(db, res2.id)
        assert len(chips2) == 1, "두 번째 예약은 처리되어야 함"

    def test_no_chip_when_schedule_missing(self, db):
        """surcharge_standard 스케줄이 없으면 칩 생성 안 함 — 예외도 없음."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=3)  # excess=1

        _make_assignment(db, res.id, room.id)
        # No surcharge schedule created

        reconcile_surcharge(db, res.id, DATE)  # should not raise

        chips = _surcharge_chips(db, res.id)
        assert len(chips) == 0

    def test_preserves_sent_standard_chip(self, db):
        """sent_at 있는 standard 칩은 보존 — 삭제 안 됨."""
        b = _make_building(db)
        room = _make_room(db, b.id, base_capacity=2)
        res = _make_reservation(db, party_size=3)  # excess=1

        tpl_std = _make_template(db, key="add_standard", name="일반추가요금")
        s_std = _make_surcharge_schedule(db, tpl_std, custom_type=SURCHARGE_STANDARD)

        _make_assignment(db, res.id, room.id)

        # Pre-insert standard chip that was already sent
        sent_chip = ReservationSmsAssignment(
            tenant_id=1, reservation_id=res.id,
            template_key=tpl_std.template_key, date=DATE,
            assigned_by="auto", schedule_id=s_std.id,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(sent_chip)
        db.flush()

        reconcile_surcharge(db, res.id, DATE)

        chips = _surcharge_chips(db, res.id)
        schedule_ids = {c.schedule_id for c in chips}
        assert s_std.id in schedule_ids, "이미 발송된 standard 칩은 보존되어야 함"
