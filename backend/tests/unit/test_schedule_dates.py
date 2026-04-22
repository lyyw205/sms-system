"""get_schedule_dates() 유닛 테스트 — 순수 함수, DB 불필요."""
import pytest
from app.services.schedule_utils import get_schedule_dates


class MockSchedule:
    def __init__(self, target_mode='first_night', date_target=None, schedule_category='standard'):
        self.target_mode = target_mode
        self.date_target = date_target
        self.schedule_category = schedule_category


class MockReservation:
    def __init__(self, check_in_date, check_out_date=None, stay_group_id=None, is_last_in_group=None):
        self.check_in_date = check_in_date
        self.check_out_date = check_out_date
        self.stay_group_id = stay_group_id
        self.is_last_in_group = is_last_in_group


class TestOnceMode:
    def test_once_returns_check_in_date(self):
        sched = MockSchedule(target_mode='first_night')
        res = MockReservation('2026-04-10')
        assert get_schedule_dates(sched, res) == ['2026-04-10']

    def test_once_no_checkout(self):
        sched = MockSchedule(target_mode='first_night')
        res = MockReservation('2026-04-10', check_out_date=None)
        assert get_schedule_dates(sched, res) == ['2026-04-10']


class TestDailyMode:
    def test_daily_3_night_stay(self):
        sched = MockSchedule(target_mode=None)
        res = MockReservation('2026-04-10', check_out_date='2026-04-13')
        result = get_schedule_dates(sched, res)
        assert result == ['2026-04-10', '2026-04-11', '2026-04-12']

    def test_daily_1_night_stay(self):
        sched = MockSchedule(target_mode=None)
        res = MockReservation('2026-04-10', check_out_date='2026-04-11')
        result = get_schedule_dates(sched, res)
        assert result == ['2026-04-10']

    def test_daily_no_checkout(self):
        sched = MockSchedule(target_mode=None)
        res = MockReservation('2026-04-10', check_out_date=None)
        result = get_schedule_dates(sched, res)
        assert result == ['2026-04-10']


class TestLastDayMode:
    def test_last_day_returns_checkout_minus_1(self):
        sched = MockSchedule(target_mode='last_night')
        res = MockReservation('2026-04-10', check_out_date='2026-04-13')
        result = get_schedule_dates(sched, res)
        assert result == ['2026-04-12']

    def test_last_day_null_checkout_returns_check_in(self):
        """check_out=None 당일 예약: check_in이 곧 마지막 투숙일."""
        sched = MockSchedule(target_mode='last_night')
        res = MockReservation('2026-04-10', check_out_date=None)
        result = get_schedule_dates(sched, res)
        assert result == ['2026-04-10']

    def test_last_day_null_checkout_no_check_in(self):
        """check_out=None, check_in=None이면 빈 리스트 반환."""
        sched = MockSchedule(target_mode='last_night')
        res = MockReservation(None, check_out_date=None)
        result = get_schedule_dates(sched, res)
        assert result == []

    def test_last_day_group_last_member(self):
        sched = MockSchedule(target_mode='last_night')
        res = MockReservation('2026-04-10', check_out_date='2026-04-13',
                              stay_group_id='g1', is_last_in_group=True)
        result = get_schedule_dates(sched, res)
        assert result == ['2026-04-12']

    def test_last_day_group_non_last_member(self):
        sched = MockSchedule(target_mode='last_night')
        res = MockReservation('2026-04-10', check_out_date='2026-04-12',
                              stay_group_id='g1', is_last_in_group=False)
        result = get_schedule_dates(sched, res)
        assert result == []


class TestEventCategory:
    def test_event_returns_check_in_date(self):
        sched = MockSchedule(schedule_category='event')
        res = MockReservation('2026-04-10', check_out_date='2026-04-13')
        result = get_schedule_dates(sched, res)
        assert result == ['2026-04-10']

    def test_event_no_check_in(self):
        sched = MockSchedule(schedule_category='event')
        res = MockReservation(None)
        result = get_schedule_dates(sched, res)
        assert result == []
