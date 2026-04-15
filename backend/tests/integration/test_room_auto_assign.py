"""room_auto_assign 관련 로직 통합 테스트 — in-memory SQLite."""
import pytest
from unittest.mock import patch
from datetime import datetime
from app.db.models import (
    Reservation, Room, Building, RoomAssignment, RoomBizItemLink,
    ReservationStatus,
)
from app.services.room_assignment import check_capacity_all_dates, assign_room
from app.services.room_auto_assign import auto_assign_rooms, daily_assign_rooms


def _make_building(db, name="본관"):
    b = Building(tenant_id=1, name=name, is_active=True)
    db.add(b)
    db.flush()
    return b


def _make_room(db, building_id, room_number="D1", is_dorm=True, bed_capacity=4):
    r = Room(
        tenant_id=1, room_number=room_number, room_type="dormitory",
        building_id=building_id, is_active=True,
        is_dormitory=is_dorm, bed_capacity=bed_capacity,
    )
    db.add(r)
    db.flush()
    return r


def _make_reservation(db, check_in="2026-04-10", check_out="2026-04-11",
                       gender=None, party_size=1, male_count=None, female_count=None):
    res = Reservation(
        tenant_id=1, customer_name="손님", phone="01012345678",
        check_in_date=check_in, check_in_time="15:00",
        check_out_date=check_out,
        status=ReservationStatus.CONFIRMED,
        gender=gender,
        party_size=party_size,
        male_count=male_count,
        female_count=female_count,
    )
    db.add(res)
    db.flush()
    return res


def _assign(db, reservation_id, room_id, date, bed_order=1):
    ra = RoomAssignment(
        tenant_id=1, reservation_id=reservation_id,
        room_id=room_id, date=date,
        assigned_by="auto", bed_order=bed_order,
    )
    db.add(ra)
    db.flush()
    return ra


def _make_biz_link(db, room_id, biz_item_id="BIZ001"):
    link = RoomBizItemLink(tenant_id=1, room_id=room_id, biz_item_id=biz_item_id)
    db.add(link)
    db.flush()
    return link


def _make_regular_room(db, building_id, room_number="R101"):
    r = Room(
        tenant_id=1, room_number=room_number, room_type="더블",
        building_id=building_id, is_active=True,
        is_dormitory=False, base_capacity=2, max_capacity=2,
    )
    db.add(r)
    db.flush()
    return r


class TestLongStayRoomPreservation:
    """단일 예약 연박자(stay_group_id 없음)의 방 유지 테스트."""

    def test_daily_assign_preserves_mid_stay_assignment(self, db):
        """daily_assign_rooms가 연박 중간 날짜 배정을 삭제하지 않는다."""
        b = _make_building(db)
        room1 = _make_regular_room(db, b.id, "R101")
        room2 = _make_regular_room(db, b.id, "R102")
        _make_biz_link(db, room1.id, "BIZ001")
        _make_biz_link(db, room2.id, "BIZ001")

        # 3박 연박 예약 (4/14~4/17)
        res = _make_reservation(db, check_in="2026-04-14", check_out="2026-04-17", gender="남")
        res.naver_biz_item_id = "BIZ001"
        db.flush()

        # 4/14에 R101로 전체 날짜 배정
        assign_room(db, res.id, room1.id, "2026-04-14", "2026-04-17",
                    assigned_by="auto", skip_sms_sync=True, skip_logging=True)
        db.flush()

        # 4/15에 daily_assign_rooms가 실행되는 상황 시뮬레이션
        # mid-stay 배정(4/15, 4/16)은 삭제되면 안 됨
        with patch("app.services.room_auto_assign.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 15, 1, 0)
            mock_dt.strptime = datetime.strptime
            daily_assign_rooms(db)

        # 4/15 배정이 여전히 R101인지 확인
        ra_15 = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == res.id,
            RoomAssignment.date == "2026-04-15",
        ).first()
        assert ra_15 is not None
        assert ra_15.room_id == room1.id, f"Expected R101 but got room_id={ra_15.room_id}"

    def test_reassign_prefers_prev_day_room_for_long_stay(self, db):
        """stay_group_id 없는 연박자도 전날 방을 우선 배정받는다."""
        b = _make_building(db)
        room1 = _make_regular_room(db, b.id, "R101")
        room2 = _make_regular_room(db, b.id, "R102")
        _make_biz_link(db, room1.id, "BIZ001")
        _make_biz_link(db, room2.id, "BIZ001")

        # 연박 예약 (4/14~4/16)
        res = _make_reservation(db, check_in="2026-04-14", check_out="2026-04-16", gender="남")
        res.naver_biz_item_id = "BIZ001"
        db.flush()

        # 4/14에 R101 배정됨 (전날 배정 기록)
        _assign(db, res.id, room1.id, "2026-04-14")

        # 4/15에 auto_assign 실행 — 전날 R101 참조해서 R101 우선
        auto_assign_rooms(db, "2026-04-15")

        ra_15 = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == res.id,
            RoomAssignment.date == "2026-04-15",
        ).first()
        assert ra_15 is not None
        assert ra_15.room_id == room1.id

    def test_checkin_day_assignment_still_cleared(self, db):
        """체크인 당일 배정은 정상적으로 삭제/재배정된다."""
        b = _make_building(db)
        room1 = _make_regular_room(db, b.id, "R101")
        _make_biz_link(db, room1.id, "BIZ001")

        # 1박 예약 (당일 체크인)
        res = _make_reservation(db, check_in="2026-04-15", check_out="2026-04-16", gender="남")
        res.naver_biz_item_id = "BIZ001"
        db.flush()

        _assign(db, res.id, room1.id, "2026-04-15")

        # daily_assign이 체크인 당일 배정은 삭제 후 재배정
        with patch("app.services.room_auto_assign.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 15, 1, 0)
            mock_dt.strptime = datetime.strptime
            daily_assign_rooms(db)

        # 재배정 후에도 배정은 존재 (삭제 후 다시 auto_assign이 배정)
        ra = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == res.id,
            RoomAssignment.date == "2026-04-15",
        ).first()
        assert ra is not None

    def test_stay_group_still_works(self, db):
        """기존 stay_group 기반 연장자 같은 방 우선 배정도 정상 동작."""
        b = _make_building(db)
        room1 = _make_regular_room(db, b.id, "R101")
        room2 = _make_regular_room(db, b.id, "R102")
        _make_biz_link(db, room1.id, "BIZ001")
        _make_biz_link(db, room2.id, "BIZ001")

        # 연장: 1박 + 1박, stay_group으로 묶임
        res1 = _make_reservation(db, check_in="2026-04-14", check_out="2026-04-15", gender="남")
        res1.naver_biz_item_id = "BIZ001"
        res1.stay_group_id = "group-abc"
        res1.stay_group_order = 0

        res2 = _make_reservation(db, check_in="2026-04-15", check_out="2026-04-16", gender="남")
        res2.naver_biz_item_id = "BIZ001"
        res2.stay_group_id = "group-abc"
        res2.stay_group_order = 1
        db.flush()

        # res1은 4/14에 R101 배정
        _assign(db, res1.id, room1.id, "2026-04-14")

        # 4/15에 auto_assign → res2가 R101 우선 배정
        auto_assign_rooms(db, "2026-04-15")

        ra = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == res2.id,
            RoomAssignment.date == "2026-04-15",
        ).first()
        assert ra is not None
        assert ra.room_id == room1.id


class TestGenderLockVerification:
    def test_dorm_not_full_male_can_enter(self, db):
        """도미토리 여유 있음 — 남성 입실 가능."""
        b = _make_building(db)
        room = _make_room(db, b.id, bed_capacity=4)
        res_male = _make_reservation(db, gender='남', party_size=1)
        _assign(db, res_male.id, room.id, "2026-04-10", bed_order=1)

        new_res = _make_reservation(db, gender='남', party_size=1)
        result = check_capacity_all_dates(db, room.id, "2026-04-10", "2026-04-11", people_count=1)
        assert result is True

    def test_dorm_full_cannot_enter(self, db):
        """도미토리 꽉 참 — 추가 입실 불가."""
        b = _make_building(db)
        room = _make_room(db, b.id, bed_capacity=2)

        res1 = _make_reservation(db, gender='남', party_size=1)
        res2 = _make_reservation(db, gender='남', party_size=1)
        _assign(db, res1.id, room.id, "2026-04-10", bed_order=1)
        _assign(db, res2.id, room.id, "2026-04-10", bed_order=2)

        result = check_capacity_all_dates(db, room.id, "2026-04-10", "2026-04-11", people_count=1)
        assert result is False


class TestPrioritySorting:
    def test_lower_bed_order_assigned_first(self, db):
        """bed_order가 낮은 슬롯부터 채워짐 확인."""
        b = _make_building(db)
        room = _make_room(db, b.id, bed_capacity=4)

        res1 = _make_reservation(db)
        assign_room(
            db, res1.id, room.id, "2026-04-10",
            assigned_by="auto", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()

        # First assignment gets bed_order=1
        ra = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == res1.id,
            RoomAssignment.date == "2026-04-10",
        ).first()
        assert ra is not None
        assert ra.bed_order == 1

    def test_second_guest_gets_next_bed_order(self, db):
        """두 번째 손님은 슬롯 2번."""
        b = _make_building(db)
        room = _make_room(db, b.id, bed_capacity=4)

        res1 = _make_reservation(db)
        assign_room(
            db, res1.id, room.id, "2026-04-10",
            assigned_by="auto", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()

        res2 = _make_reservation(db)
        assign_room(
            db, res2.id, room.id, "2026-04-10",
            assigned_by="auto", skip_sms_sync=True, skip_logging=True,
        )
        db.flush()

        ra2 = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == res2.id,
            RoomAssignment.date == "2026-04-10",
        ).first()
        assert ra2 is not None
        assert ra2.bed_order == 2
