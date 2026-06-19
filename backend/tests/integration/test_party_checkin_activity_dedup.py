"""party_checkin §D4 dedup 검증 (Option A).

규칙: 동일 phone 의 비-activity 행이 명단에 있으면 그 phone 의 activity 행은
count_in_total=False (인원 미합산). activity 단독 참여는 count_in_total=True.
행 자체는 항상 표시(체크인 가능).
"""
import asyncio

from app.api.party_checkin import get_party_checkin_list
from app.db.models import Reservation, ReservationStatus

D = "2026-08-01"


def _res(db, *, section, party_type=None, male=0, female=0, phone="010", name="g"):
    r = Reservation(
        tenant_id=1,
        customer_name=name,
        phone=phone,
        check_in_date=D,
        check_out_date=None,
        check_in_time="15:00",
        status=ReservationStatus.CONFIRMED,
        section=section,
        party_type=party_type,
        male_count=male,
        female_count=female,
    )
    db.add(r)
    db.flush()
    return r


def _list(db):
    return asyncio.run(
        get_party_checkin_list(date=D, party_source="stable", db=db, current_user=None)
    )


def test_activity_only_counted(db):
    _res(db, section="activity", party_type="2", male=3, female=0, phone="p1")
    items = _list(db)
    act = [i for i in items if i.section == "activity"]
    assert len(act) == 1
    assert act[0].count_in_total is True  # 단독 참여 → 합산


def test_room_plus_activity_dedup(db):
    _res(db, section="room", party_type="2", male=2, female=0, phone="dup", name="A객실")
    _res(db, section="activity", party_type="2", male=2, female=0, phone="dup", name="A활동")
    items = _list(db)
    room = [i for i in items if i.section == "room"][0]
    act = [i for i in items if i.section == "activity"][0]
    # 둘 다 명단 표시
    assert room.count_in_total is True
    assert act.count_in_total is False  # 동일 phone 객실행 존재 → 미합산


def test_room_without_party_does_not_suppress_activity(db):
    # 객실행이 party_type 없으면 명단에 안 뜸 → activity 단독 → 합산 유지
    _res(db, section="room", party_type=None, male=2, female=0, phone="dup", name="B객실")
    _res(db, section="activity", party_type="2", male=2, female=0, phone="dup", name="B활동")
    items = _list(db)
    assert all(i.section != "room" for i in items)  # 객실행 미등장
    act = [i for i in items if i.section == "activity"][0]
    assert act.count_in_total is True
