"""_filter_last_day() 통합 테스트 — Reservation ORM 객체 필요."""
import pytest
from app.db.models import Reservation, ReservationStatus
from app.scheduler.template_scheduler import TemplateScheduleExecutor


def _make_reservation(db, name, check_in, check_out=None, stay_group_id=None):
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


class TestFilterLastDay:
    def _exec(self, db):
        return TemplateScheduleExecutor(db, tenant=None)

    def test_standalone_last_day(self, db):
        """단독 투숙: checkout - 1 == target_date이면 포함."""
        r = _make_reservation(db, "김철수", "2026-04-10", "2026-04-12")
        executor = self._exec(db)
        # target=4/11 → checkout(4/12) - 1 = 4/11 → 포함
        result = executor._filter_last_day([r], "2026-04-11")
        assert len(result) == 1
        assert result[0].id == r.id

    def test_standalone_not_last_day(self, db):
        """단독 투숙: checkout - 1 != target_date이면 제외."""
        r = _make_reservation(db, "김철수", "2026-04-10", "2026-04-12")
        executor = self._exec(db)
        # target=4/10 → checkout(4/12) - 1 = 4/11 ≠ 4/10 → 제외
        result = executor._filter_last_day([r], "2026-04-10")
        assert len(result) == 0

    def test_group_last_day(self, db):
        """연장 그룹: 그룹 내 max(checkout) - 1 == target이면 포함."""
        group_id = "group-1"
        r1 = _make_reservation(db, "연장1", "2026-04-10", "2026-04-12", stay_group_id=group_id)
        r2 = _make_reservation(db, "연장2", "2026-04-12", "2026-04-14", stay_group_id=group_id)
        executor = self._exec(db)
        # 그룹 max checkout = 4/14, last_day = 4/13
        result = executor._filter_last_day([r1, r2], "2026-04-13")
        assert len(result) == 2

    def test_group_not_last_day(self, db):
        """연장 그룹: 중간 날짜면 제외."""
        group_id = "group-2"
        r1 = _make_reservation(db, "연장1", "2026-04-10", "2026-04-12", stay_group_id=group_id)
        r2 = _make_reservation(db, "연장2", "2026-04-12", "2026-04-14", stay_group_id=group_id)
        executor = self._exec(db)
        result = executor._filter_last_day([r1, r2], "2026-04-11")
        assert len(result) == 0

    def test_null_checkout_same_day_included(self, db):
        """checkout=NULL 당일 예약: check_in == target_date이면 포함."""
        r = _make_reservation(db, "체크아웃없음", "2026-04-10", None)
        executor = self._exec(db)
        result = executor._filter_last_day([r], "2026-04-10")
        assert len(result) == 1
        assert result[0].id == r.id

    def test_null_checkout_different_day_excluded(self, db):
        """checkout=NULL 당일 예약: check_in != target_date이면 제외."""
        r = _make_reservation(db, "체크아웃없음", "2026-04-10", None)
        executor = self._exec(db)
        result = executor._filter_last_day([r], "2026-04-11")
        assert len(result) == 0


class TestFilterLastDayWithDateTarget:
    """last_day + yesterday/today date_target 조합 케이스."""

    def _exec(self, db):
        from app.scheduler.template_scheduler import TemplateScheduleExecutor
        return TemplateScheduleExecutor(db, tenant=None)

    def test_last_day_yesterday_target(self, db):
        """checkout=오늘 → last_day=어제 → target_date=yesterday 일치."""
        from datetime import date, timedelta
        from app.config import today_kst_date
        today = today_kst_date()
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")

        # check_out=오늘이면 last_day = 오늘-1 = 어제
        r = _make_reservation(db, "어제퇴실", (today - timedelta(days=2)).strftime("%Y-%m-%d"),
                              today_str)
        executor = self._exec(db)
        result = executor._filter_last_day([r], yesterday)
        assert len(result) == 1
        assert result[0].id == r.id

    def test_last_day_today_target(self, db):
        """checkout=내일 → last_day=오늘 → target_date=today 일치."""
        from datetime import date, timedelta
        from app.config import today_kst_date
        today = today_kst_date()
        today_str = today.strftime("%Y-%m-%d")
        tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")

        # check_out=내일이면 last_day = 오늘
        r = _make_reservation(db, "오늘퇴실", (today - timedelta(days=1)).strftime("%Y-%m-%d"),
                              tomorrow)
        executor = self._exec(db)
        result = executor._filter_last_day([r], today_str)
        assert len(result) == 1
        assert result[0].id == r.id

    def test_last_day_yesterday_wrong_target_excluded(self, db):
        """checkout=모레 → last_day=내일 → target_date=yesterday 불일치."""
        from datetime import date, timedelta
        from app.config import today_kst_date
        today = today_kst_date()
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        day_after_tomorrow = (today + timedelta(days=2)).strftime("%Y-%m-%d")

        r = _make_reservation(db, "모레퇴실", today.strftime("%Y-%m-%d"), day_after_tomorrow)
        executor = self._exec(db)
        result = executor._filter_last_day([r], yesterday)
        assert len(result) == 0
