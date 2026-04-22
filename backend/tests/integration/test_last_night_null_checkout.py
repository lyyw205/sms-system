"""회귀 테스트: last_night 모드에서 check_out_date=None 예약 처리.

배경:
    파티만 예약이 room 섹션으로 이동되면 section='room', RoomAssignment 존재,
    하지만 check_out_date=None 인 상태가 됨. 기존 로직은 이를 스킵했으나
    수정 후에는 check_in_date == target_date 이면 마지막 투숙일로 간주해 포함.

커버 범위:
    A) get_schedule_dates — NULL checkout → check_in 반환
    B) _filter_last_day — target == check_in → 포함
    C) _filter_last_day — target != check_in → 제외
    D) get_schedule_dates — 정상 연박 예약 회귀 방지
    E) _filter_last_day — 그룹 내 NULL checkout 혼재 코너 케이스
"""
import pytest
from app.db.models import Reservation, ReservationStatus
from app.services.schedule_utils import get_schedule_dates
from app.scheduler.template_scheduler import TemplateScheduleExecutor


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

class MockSchedule:
    """get_schedule_dates 호출용 최소 스케줄 mock."""
    def __init__(self, target_mode='last_night', schedule_category='standard'):
        self.target_mode = target_mode
        self.schedule_category = schedule_category


class MockReservation:
    """get_schedule_dates 호출용 최소 예약 mock (DB 불필요)."""
    def __init__(self, check_in_date, check_out_date=None,
                 stay_group_id=None, is_last_in_group=None):
        self.check_in_date = check_in_date
        self.check_out_date = check_out_date
        self.stay_group_id = stay_group_id
        self.is_last_in_group = is_last_in_group


def _make_orm_reservation(db, name, check_in, check_out=None, stay_group_id=None):
    """실제 ORM Reservation 객체 생성 — _filter_last_day 테스트용."""
    res = Reservation(
        tenant_id=1, customer_name=name, phone="01000000000",
        check_in_date=check_in, check_in_time="15:00",
        check_out_date=check_out,
        status=ReservationStatus.CONFIRMED,
        stay_group_id=stay_group_id,
    )
    db.add(res)
    db.flush()
    return res


# ---------------------------------------------------------------------------
# A: get_schedule_dates — NULL checkout
# ---------------------------------------------------------------------------

class TestGetScheduleDatesNullCheckout:
    """get_schedule_dates() last_night 모드 + check_out=None 케이스."""

    def test_A_null_checkout_returns_check_in_date(self):
        """테스트 A: check_out=None 당일 예약 → [check_in_date] 반환 (빈 리스트 아님)."""
        sched = MockSchedule(target_mode='last_night')
        res = MockReservation(check_in_date='2026-04-21', check_out_date=None)

        result = get_schedule_dates(sched, res)

        assert result == ['2026-04-21'], (
            "check_out=None 당일 예약의 last_night은 check_in_date를 반환해야 합니다."
        )

    def test_A_null_checkout_null_checkin_returns_empty(self):
        """check_in도 None이면 빈 리스트 — 안전 폴백."""
        sched = MockSchedule(target_mode='last_night')
        res = MockReservation(check_in_date=None, check_out_date=None)

        result = get_schedule_dates(sched, res)

        assert result == []


# ---------------------------------------------------------------------------
# B & C: _filter_last_day — NULL checkout 포함/제외
# ---------------------------------------------------------------------------

class TestFilterLastDayNullCheckout:
    """_filter_last_day() — check_out=None 예약의 포함/제외 로직."""

    def _exec(self, db):
        return TemplateScheduleExecutor(db, tenant=None)

    def test_B_null_checkout_target_equals_check_in_included(self, db):
        """테스트 B: check_out=None, target_date == check_in → 포함."""
        r = _make_orm_reservation(db, "파티이동예약", "2026-04-21", check_out=None)
        executor = self._exec(db)

        result = executor._filter_last_day([r], "2026-04-21")

        assert len(result) == 1
        assert result[0].id == r.id, (
            "check_in==target_date인 NULL checkout 예약은 last_night 대상에 포함돼야 합니다."
        )

    def test_C_null_checkout_target_differs_from_check_in_excluded(self, db):
        """테스트 C: check_out=None, target_date != check_in → 제외."""
        r = _make_orm_reservation(db, "파티이동예약", "2026-04-21", check_out=None)
        executor = self._exec(db)

        result = executor._filter_last_day([r], "2026-04-20")

        assert len(result) == 0, (
            "check_in != target_date인 NULL checkout 예약은 제외돼야 합니다."
        )

    def test_C2_null_checkout_future_target_excluded(self, db):
        """check_out=None, target_date가 check_in보다 미래여도 제외."""
        r = _make_orm_reservation(db, "파티이동예약", "2026-04-21", check_out=None)
        executor = self._exec(db)

        result = executor._filter_last_day([r], "2026-04-22")

        assert len(result) == 0


# ---------------------------------------------------------------------------
# D: 정상 연박 예약 회귀 방지
# ---------------------------------------------------------------------------

class TestFilterLastDayNormalStay:
    """테스트 D: check_out이 있는 정상 연박 예약은 기존 동작 그대로."""

    def _exec(self, db):
        return TemplateScheduleExecutor(db, tenant=None)

    def test_D_normal_stay_last_night_is_checkout_minus_1(self, db):
        """check_in=4/20, check_out=4/23 → last_night = 4/22 (checkout-1)."""
        r = _make_orm_reservation(db, "연박손님", "2026-04-20", check_out="2026-04-23")
        executor = self._exec(db)

        result_hit = executor._filter_last_day([r], "2026-04-22")
        result_miss = executor._filter_last_day([r], "2026-04-21")

        assert len(result_hit) == 1, "checkout-1 날짜에 포함돼야 합니다."
        assert len(result_miss) == 0, "중간 날짜에 포함되면 안 됩니다."

    def test_D_get_schedule_dates_normal_stay(self):
        """get_schedule_dates: check_out 있는 연박 → checkout-1 반환."""
        sched = MockSchedule(target_mode='last_night')
        res = MockReservation(check_in_date='2026-04-20', check_out_date='2026-04-23')

        result = get_schedule_dates(sched, res)

        assert result == ['2026-04-22'], (
            "정상 연박 예약의 last_night은 checkout-1이어야 합니다."
        )


# ---------------------------------------------------------------------------
# E: stay_group 내 NULL checkout 혼재 코너 케이스
# ---------------------------------------------------------------------------

class TestFilterLastDayGroupWithNullCheckout:
    """테스트 E: 그룹 내 일부 예약만 check_out=None인 혼재 케이스."""

    def _exec(self, db):
        return TemplateScheduleExecutor(db, tenant=None)

    def test_E_group_null_checkout_member_excluded_on_non_check_in_date(self, db):
        """그룹 내 NULL checkout 멤버는 자신의 check_in과 target이 다르면 제외."""
        group_id = "group-null-mix"
        r1 = _make_orm_reservation(db, "연장1", "2026-04-20", "2026-04-23", stay_group_id=group_id)
        # r2는 check_out=None (파티이동 케이스)
        r2 = _make_orm_reservation(db, "파티이동", "2026-04-20", None, stay_group_id=group_id)
        executor = self._exec(db)

        # 그룹 max checkout = 4/23 → last_night = 4/22
        # r1은 group 로직으로 4/22에 포함, r2는 check_out=None이므로 check_in(4/20) 비교
        result_at_22 = executor._filter_last_day([r1, r2], "2026-04-22")
        result_at_20 = executor._filter_last_day([r1, r2], "2026-04-20")

        # r1은 그룹 last_night(4/22)에 포함
        assert any(r.id == r1.id for r in result_at_22), (
            "그룹 내 정상 멤버는 group last_night에 포함돼야 합니다."
        )
        # r2는 check_in(4/20) == target(4/22) 불일치 → 제외
        assert not any(r.id == r2.id for r in result_at_22), (
            "NULL checkout 멤버는 자신의 check_in이 target과 다르면 제외돼야 합니다."
        )
        # r2는 check_in(4/20) == target(4/20) 일치 → 포함
        assert any(r.id == r2.id for r in result_at_20), (
            "NULL checkout 멤버는 check_in == target_date이면 포함돼야 합니다."
        )
