"""activity_stats_filter (§6-G / D1 / D8 Option A) 동작 검증.

규칙: 통계 SUM 에서
  - 비-activity 예약: 항상 포함
  - activity 예약: 그 날짜 effective party_type ∈ {'1','2','2차만'} 일 때만 포함
    (effective = COALESCE(ReservationDailyInfo.party_type[date], Reservation.party_type))
  - activity 미참여(party_type NULL / 'X'): 제외
"""
from sqlalchemy import func

from app.db.models import (
    Reservation,
    ReservationDailyInfo,
    ReservationStatus,
)
from app.services.filters import stay_coverage_filter, activity_stats_filter

D = "2026-07-01"


def _res(db, *, section, check_in=D, check_out=None, party_type=None, male=0, female=0, phone="010"):
    r = Reservation(
        tenant_id=1,
        customer_name="g",
        phone=phone,
        check_in_date=check_in,
        check_out_date=check_out,
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


def _daily(db, res, d, party_type):
    di = ReservationDailyInfo(tenant_id=1, reservation_id=res.id, date=d, party_type=party_type)
    db.add(di)
    db.flush()
    return di


def _sum(db, d):
    row = db.query(
        func.coalesce(func.sum(Reservation.male_count), 0),
        func.coalesce(func.sum(Reservation.female_count), 0),
    ).filter(
        stay_coverage_filter(d),
        activity_stats_filter(db, d),
        Reservation.status == ReservationStatus.CONFIRMED,
    ).first()
    return int(row[0]), int(row[1])


def test_room_included(db):
    _res(db, section="room", check_out="2026-07-02", male=2, female=1)
    assert _sum(db, D) == (2, 1)


def test_activity_no_party_excluded(db):
    _res(db, section="activity", male=3, female=2)
    assert _sum(db, D) == (0, 0)


def test_activity_res_party_type_included(db):
    # Reservation.party_type 직접 세팅(daily 없음) → COALESCE 가 res 값 사용 → 포함
    _res(db, section="activity", party_type="2", male=1, female=1)
    assert _sum(db, D) == (1, 1)


def test_activity_daily_party_included(db):
    r = _res(db, section="activity", male=4, female=0)
    _daily(db, r, D, "2차만")
    assert _sum(db, D) == (4, 0)


def test_activity_daily_X_overrides_res(db):
    # res.party_type='2' 이지만 그날 daily='X'(미참여) → COALESCE daily 우선 → 제외
    r = _res(db, section="activity", party_type="2", male=5, female=5)
    _daily(db, r, D, "X")
    assert _sum(db, D) == (0, 0)


def test_activity_daily_only_other_date_not_counted(db):
    # 다른 날짜에만 daily party_type → target_date 에는 미참여로 제외 (§5 엣지: stay_coverage)
    r = _res(db, section="activity", male=2, female=0)
    _daily(db, r, "2026-07-05", "2")
    assert _sum(db, D) == (0, 0)


def test_mixed(db):
    _res(db, section="room", check_out="2026-07-02", male=2, female=0, phone="a")
    _res(db, section="activity", male=10, female=10, phone="b")  # 미참여 → 제외
    _res(db, section="activity", party_type="1", male=1, female=0, phone="c")  # 참여 → 포함
    assert _sum(db, D) == (3, 0)
