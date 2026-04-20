"""이중배정 밀어내기 정책 통합 테스트 — in-memory SQLite."""
from unittest.mock import patch
from datetime import datetime
from app.db.models import (
    Reservation, Room, Building, RoomAssignment, ReservationStatus,
)
from app.services.room_assignment import assign_room


def _make_building(db):
    b = Building(tenant_id=1, name="본관", is_active=True)
    db.add(b)
    db.flush()
    return b


def _make_regular_room(db, building_id, room_number="R101"):
    r = Room(
        tenant_id=1, room_number=room_number, room_type="standard",
        building_id=building_id, is_active=True,
        is_dormitory=False, base_capacity=2, max_capacity=2,
    )
    db.add(r)
    db.flush()
    return r


def _make_reservation(db, section="unassigned", party_size=1):
    res = Reservation(
        tenant_id=1, customer_name="손님", phone="01012345678",
        check_in_date="2026-04-10", check_in_time="15:00",
        check_out_date="2026-04-12",
        status=ReservationStatus.CONFIRMED,
        section=section,
        party_size=party_size,
    )
    db.add(res)
    db.flush()
    return res


def _assign_direct(db, reservation_id, room_id, date):
    ra = RoomAssignment(
        tenant_id=1, reservation_id=reservation_id,
        room_id=room_id, date=date,
        assigned_by="manual", bed_order=1,
    )
    db.add(ra)
    db.flush()
    return ra


class TestPushOutPolicy:
    def test_future_double_booking_evicts_existing(self, db):
        """일반실 미래 이중배정 시 기존자 section=unassigned로 이동."""
        b = _make_building(db)
        room = _make_regular_room(db, b.id)

        res_existing = _make_reservation(db, section="room")
        _assign_direct(db, res_existing.id, room.id, "2026-04-20")

        res_new = _make_reservation(db, section="unassigned")

        # "Today" is before 4/20 so push-out applies
        with patch("app.services.room_assignment.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 10, 10, 0)
            mock_dt.strptime = datetime.strptime
            assignments, pushed_out = assign_room(
                db, res_new.id, room.id, "2026-04-20",
                assigned_by="manual", skip_sms_sync=True, skip_logging=True,
            )
        db.flush()

        # Existing reservation should now be unassigned
        db.refresh(res_existing)
        assert res_existing.section == "unassigned"

        # pushed_out list should contain the evicted reservation
        assert len(pushed_out) >= 1
        evicted_ids = [p["reservation_id"] for p in pushed_out]
        assert res_existing.id in evicted_ids

    def test_today_double_booking_kept_both(self, db):
        """당일 이중배정은 경고만 — 기존 배정 삭제하지 않음."""
        b = _make_building(db)
        room = _make_regular_room(db, b.id)

        res_existing = _make_reservation(db, section="room")
        _assign_direct(db, res_existing.id, room.id, "2026-04-10")

        res_new = _make_reservation(db, section="unassigned")

        # "Today" is 4/10 so push-out NOT applied
        with patch("app.services.room_assignment.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 10, 10, 0)
            mock_dt.strptime = datetime.strptime
            assignments, pushed_out = assign_room(
                db, res_new.id, room.id, "2026-04-10",
                assigned_by="manual", skip_sms_sync=True, skip_logging=True,
            )
        db.flush()

        # Existing reservation section should NOT have changed
        db.refresh(res_existing)
        assert res_existing.section == "room"

        # No one was pushed out
        assert pushed_out == []

    def test_pushed_out_contains_info(self, db):
        """assign_room 리턴의 pushed_out 리스트가 reservation_id, date, cause 포함."""
        b = _make_building(db)
        room = _make_regular_room(db, b.id)

        res_existing = _make_reservation(db, section="room")
        _assign_direct(db, res_existing.id, room.id, "2026-04-25")

        res_new = _make_reservation(db, section="unassigned")

        with patch("app.services.room_assignment.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 10, 10, 0)
            mock_dt.strptime = datetime.strptime
            _, pushed_out = assign_room(
                db, res_new.id, room.id, "2026-04-25",
                assigned_by="manual", skip_sms_sync=True, skip_logging=True,
            )

        assert len(pushed_out) == 1
        p = pushed_out[0]
        assert "reservation_id" in p
        assert "date" in p
        assert "cause" in p
        assert p["date"] == "2026-04-25"
