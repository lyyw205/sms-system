"""assign_room() 의 표시용 비밀번호 저장/재사용 규칙 통합 테스트.

설계:
  room_password           — Room.door_password 단순 복사 (불변)
  room_password_prefixed  — 랜덤 prefix 가 붙은 표시용 버전. 재사용 규칙:
    P1: 같은 (room, date) 에 다른 예약의 prefixed 값이 이미 있음 → 재사용
        (도미토리 공동 투숙, 수동 복수 배정)
    P2: 같은 reservation + 같은 방 다른 날짜 배정이 있음 → 재사용
        (연박자 재발송 안전망)
    P3: 둘 다 없음 → build_prefixed_password() 로 신규 생성
"""
from app.db.models import (
    Building,
    Reservation,
    ReservationStatus,
    Room,
    RoomAssignment,
)
from app.services.room_assignment import assign_room


def _make_building(db):
    b = Building(tenant_id=1, name="본관", is_active=True)
    db.add(b)
    db.flush()
    return b


def _make_room(db, building_id, *, room_number="101", is_dorm=False, door_password="404", capacity=2):
    r = Room(
        tenant_id=1,
        room_number=room_number,
        room_type="standard",
        building_id=building_id,
        is_active=True,
        is_dormitory=is_dorm,
        bed_capacity=capacity,
        door_password=door_password,
    )
    db.add(r)
    db.flush()
    return r


def _make_reservation(db, *, name="손님", phone="01012345678", check_in="2026-04-10", check_out=None, section="unassigned"):
    res = Reservation(
        tenant_id=1,
        customer_name=name,
        phone=phone,
        check_in_date=check_in,
        check_in_time="15:00",
        check_out_date=check_out,
        status=ReservationStatus.CONFIRMED,
        section=section,
    )
    db.add(res)
    db.flush()
    return res


class TestBasePassword:
    def test_room_password_is_plain_copy_of_door_password(self, db):
        """base room_password 는 Room.door_password 를 그대로 복사 — prefix 없음."""
        b = _make_building(db)
        room = _make_room(db, b.id, door_password="9999")
        res = _make_reservation(db)

        assignments = assign_room(
            db, res.id, room.id, "2026-04-10",
            assigned_by="manual", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()
        assert assignments[0].room_password == "9999"

    def test_empty_door_password_yields_empty_base(self, db):
        b = _make_building(db)
        room = _make_room(db, b.id, door_password=None)
        res = _make_reservation(db)

        assignments = assign_room(
            db, res.id, room.id, "2026-04-10",
            assigned_by="manual", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()
        assert assignments[0].room_password == ""


class TestPrefixedPasswordReuse:
    def test_dormitory_multiple_parties_share_prefixed(self, db):
        """도미토리 한 방에 여러 예약자 → 전원 같은 prefixed 번호."""
        b = _make_building(db)
        dorm = _make_room(db, b.id, room_number="D101", is_dorm=True, capacity=4, door_password="777")

        r1 = _make_reservation(db, name="손님1", phone="01011111111")
        r2 = _make_reservation(db, name="손님2", phone="01022222222")
        r3 = _make_reservation(db, name="손님3", phone="01033333333")

        for res in (r1, r2, r3):
            assign_room(db, res.id, dorm.id, "2026-04-10",
                        assigned_by="auto", skip_sms_sync=True, skip_logging=True)
        db.flush()

        prefixed_set = {
            a.room_password_prefixed for a in db.query(RoomAssignment)
            .filter(RoomAssignment.room_id == dorm.id, RoomAssignment.date == "2026-04-10")
            .all()
        }
        assert len(prefixed_set) == 1, f"도미토리 전원 동일 prefixed 여야 함: {prefixed_set}"

    def test_manual_double_booking_shares_prefixed(self, db):
        """일반 객실에 수동으로 2팀 배정 → 같은 prefixed 번호."""
        b = _make_building(db)
        room = _make_room(db, b.id)

        r1 = _make_reservation(db, name="A", phone="01011111111")
        r2 = _make_reservation(db, name="B", phone="01022222222")

        assign_room(db, r1.id, room.id, "2026-04-10",
                    assigned_by="manual", skip_sms_sync=True, skip_logging=True)
        assign_room(db, r2.id, room.id, "2026-04-10",
                    assigned_by="manual", skip_sms_sync=True, skip_logging=True)
        db.flush()

        rows = db.query(RoomAssignment).filter(
            RoomAssignment.room_id == room.id,
            RoomAssignment.date == "2026-04-10",
        ).all()
        assert len(rows) == 2
        assert rows[0].room_password_prefixed == rows[1].room_password_prefixed

    def test_long_stay_same_reservation_same_prefixed(self, db):
        """연박자 → 체류 전 날짜 같은 prefixed 번호."""
        b = _make_building(db)
        room = _make_room(db, b.id)
        res = _make_reservation(db, check_in="2026-04-10", check_out="2026-04-13")

        assignments = assign_room(
            db, res.id, room.id, "2026-04-10", end_date="2026-04-13",
            assigned_by="manual", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()

        prefixed_set = {a.room_password_prefixed for a in assignments}
        assert len(prefixed_set) == 1
        assert len(assignments) == 3

    def test_different_date_different_reservation_new_prefix(self, db):
        """다른 예약자 × 다른 날짜 → 재사용 규칙에 안 걸려 새 prefix 생성."""
        b = _make_building(db)
        room = _make_room(db, b.id, door_password="404")

        r1 = _make_reservation(db, name="A", phone="01011111111", check_in="2026-04-10")
        r2 = _make_reservation(db, name="B", phone="01022222222", check_in="2026-04-11")

        assign_room(db, r1.id, room.id, "2026-04-10",
                    assigned_by="manual", skip_sms_sync=True, skip_logging=True)
        assign_room(db, r2.id, room.id, "2026-04-11",
                    assigned_by="manual", skip_sms_sync=True, skip_logging=True)
        db.flush()

        r1_row = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == r1.id, RoomAssignment.date == "2026-04-10",
        ).first()
        r2_row = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == r2.id, RoomAssignment.date == "2026-04-11",
        ).first()
        # base 는 둘 다 그대로
        assert r1_row.room_password == "404"
        assert r2_row.room_password == "404"
        # prefixed 는 둘 다 5글자 (2 prefix + 3 base) 이고 404 로 끝남
        assert r1_row.room_password_prefixed.endswith("404")
        assert r2_row.room_password_prefixed.endswith("404")
        assert len(r1_row.room_password_prefixed) == 5
        assert len(r2_row.room_password_prefixed) == 5

    def test_same_assignment_reassigned_keeps_prefixed(self, db):
        """같은 (reservation, room, dates) 재배정 시 prefixed 값 유지.

        운영자가 실수로 drag 반복, 또는 연박 연장처럼 기존 dates 가 포함된
        재호출이 일어나도 prefixed 번호가 바뀌지 않아야 함 — 이미 SMS 로
        나간 번호와 DB 값이 달라지는 상황 방지.
        """
        b = _make_building(db)
        room = _make_room(db, b.id)
        res = _make_reservation(db, check_in="2026-04-10", check_out="2026-04-12")

        first = assign_room(
            db, res.id, room.id, "2026-04-10", end_date="2026-04-12",
            assigned_by="manual", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()
        original = first[0].room_password_prefixed

        # 같은 조건으로 다시 호출 (재 drag / 연박 연장)
        second = assign_room(
            db, res.id, room.id, "2026-04-10", end_date="2026-04-13",
            assigned_by="manual", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()

        # 모든 날짜가 원래 prefix 와 동일해야 함
        for a in second:
            assert a.room_password_prefixed == original, (
                f"재배정 후 prefix 바뀜: {a.date} = {a.room_password_prefixed}, 원래 {original}"
            )

    def test_base_and_prefixed_coexist_on_same_row(self, db):
        """한 row 에 base 와 prefixed 가 각자 저장됨."""
        b = _make_building(db)
        room = _make_room(db, b.id, door_password="404")
        res = _make_reservation(db)

        assignments = assign_room(
            db, res.id, room.id, "2026-04-10",
            assigned_by="manual", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()
        ra = assignments[0]
        assert ra.room_password == "404"
        assert ra.room_password_prefixed.endswith("404")
        assert ra.room_password_prefixed != ra.room_password
