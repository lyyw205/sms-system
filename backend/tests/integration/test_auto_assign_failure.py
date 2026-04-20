"""auto_assign_rooms() 실패 사유 분류 통합 테스트 — in-memory SQLite."""
from app.db.models import (
    Reservation, Room, Building, RoomAssignment, RoomBizItemLink,
    ReservationStatus,
)
from app.services.room_auto_assign import auto_assign_rooms


def _make_building(db, name="본관"):
    b = Building(tenant_id=1, name=name, is_active=True)
    db.add(b)
    db.flush()
    return b


def _make_dorm_room(db, building_id, room_number="D1", bed_capacity=4):
    r = Room(
        tenant_id=1, room_number=room_number, room_type="dormitory",
        building_id=building_id, is_active=True,
        is_dormitory=True, bed_capacity=bed_capacity,
    )
    db.add(r)
    db.flush()
    return r


def _make_regular_room(db, building_id, room_number="R101"):
    r = Room(
        tenant_id=1, room_number=room_number, room_type="standard",
        building_id=building_id, is_active=True,
        is_dormitory=False, base_capacity=2, max_capacity=2,
    )
    db.add(r)
    db.flush()
    return r


def _make_reservation(db, check_in="2026-04-10", check_out="2026-04-11",
                       gender=None, party_size=1, biz_item_id="BIZ001"):
    res = Reservation(
        tenant_id=1, customer_name="손님", phone="01012345678",
        check_in_date=check_in, check_in_time="15:00",
        check_out_date=check_out,
        status=ReservationStatus.CONFIRMED,
        gender=gender,
        party_size=party_size,
        naver_biz_item_id=biz_item_id,
    )
    db.add(res)
    db.flush()
    return res


def _make_biz_link(db, room_id, biz_item_id="BIZ001"):
    link = RoomBizItemLink(tenant_id=1, room_id=room_id, biz_item_id=biz_item_id)
    db.add(link)
    db.flush()
    return link


def _make_assignment(db, reservation_id, room_id, date, bed_order=1):
    ra = RoomAssignment(
        tenant_id=1, reservation_id=reservation_id,
        room_id=room_id, date=date,
        assigned_by="auto", bed_order=bed_order,
    )
    db.add(ra)
    db.flush()
    return ra


class TestAutoAssignFailureReasons:
    def test_no_candidate_rooms_failure(self, db):
        """biz_item_id에 매칭 방 없으면 no_candidate_rooms 실패 기록."""
        b = _make_building(db)
        room = _make_dorm_room(db, b.id)
        # Link room to BIZ_OTHER, not BIZ001
        _make_biz_link(db, room.id, biz_item_id="BIZ_OTHER")

        res = _make_reservation(db, biz_item_id="BIZ001")  # no matching room

        result = auto_assign_rooms(db, "2026-04-10")

        assert result["unassigned"] >= 1
        # Verify no assignment was created for this reservation
        ra = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == res.id,
        ).first()
        assert ra is None

    def test_gender_lock_failure(self, db):
        """도미토리 성별 충돌 시 배정 실패."""
        b = _make_building(db)
        room = _make_dorm_room(db, b.id, bed_capacity=4)
        _make_biz_link(db, room.id)

        # Pre-fill with female guest
        existing_res = _make_reservation(db, gender="여", party_size=1)
        _make_assignment(db, existing_res.id, room.id, "2026-04-10", bed_order=1)

        # Male guest tries to enter same dorm
        male_res = _make_reservation(db, gender="남", party_size=1)

        result = auto_assign_rooms(db, "2026-04-10")

        ra = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == male_res.id,
            RoomAssignment.date == "2026-04-10",
        ).first()
        assert ra is None

    def test_capacity_full_failure(self, db):
        """도미토리 용량 초과 시 배정 실패."""
        b = _make_building(db)
        room = _make_dorm_room(db, b.id, bed_capacity=1)
        _make_biz_link(db, room.id)

        # Fill the only bed
        existing_res = _make_reservation(db, gender="남", party_size=1)
        _make_assignment(db, existing_res.id, room.id, "2026-04-10", bed_order=1)

        # Another male cannot enter (capacity full)
        new_res = _make_reservation(db, gender="남", party_size=1)

        result = auto_assign_rooms(db, "2026-04-10")

        ra = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == new_res.id,
            RoomAssignment.date == "2026-04-10",
        ).first()
        assert ra is None

    def test_success_and_failure_coexist(self, db):
        """성공 레코드와 실패 레코드가 같은 실행 결과에 공존."""
        b = _make_building(db)
        room = _make_dorm_room(db, b.id, bed_capacity=1)
        _make_biz_link(db, room.id, biz_item_id="BIZ001")

        # res1 will succeed (empty room)
        res1 = _make_reservation(db, gender="남", party_size=1, biz_item_id="BIZ001")
        # res2 will fail (capacity full after res1)
        res2 = _make_reservation(db, gender="남", party_size=1, biz_item_id="BIZ001")

        result = auto_assign_rooms(db, "2026-04-10")

        # Exactly one should be assigned, one should fail
        assigned_count = db.query(RoomAssignment).filter(
            RoomAssignment.date == "2026-04-10",
            RoomAssignment.reservation_id.in_([res1.id, res2.id]),
        ).count()
        assert assigned_count == 1
        assert result["assigned"] >= 1
