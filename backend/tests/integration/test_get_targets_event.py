"""_get_targets_event() 통합 테스트 — in-memory SQLite."""
import pytest
from datetime import datetime, timedelta, timezone, date
from app.db.models import (
    Reservation, ReservationStatus, MessageTemplate, TemplateSchedule,
    ReservationSmsAssignment,
)
from app.scheduler.template_scheduler import TemplateScheduleExecutor
from app.config import today_kst


def _executor(db):
    return TemplateScheduleExecutor(db, tenant=None)


def _future(days=3):
    """체크인 임박 안전가드(check_in_date > today)를 통과하는 미래 날짜."""
    return (date.fromisoformat(today_kst()) + timedelta(days=days)).isoformat()


def _make_template(db, key="evt_tpl"):
    tpl = MessageTemplate(
        tenant_id=1, template_key=key, name="Test", content="hello", is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _make_event_schedule(db, template, hours_since_booking=None, gender_filter=None,
                          max_checkin_days=None, exclude_sent=False):
    sched = TemplateSchedule(
        tenant_id=1, template_id=template.id, schedule_name="evt_test",
        schedule_type="hourly", hour=None, minute=0,
        schedule_category='event',
        hours_since_booking=hours_since_booking,
        gender_filter=gender_filter,
        max_checkin_days=max_checkin_days,
        exclude_sent=exclude_sent,
        is_active=True,
    )
    db.add(sched)
    db.flush()
    return sched


def _make_reservation(db, check_in=None, confirmed_at=None, gender=None,
                       status=ReservationStatus.CONFIRMED, is_long_stay=False,
                       male_count=None, female_count=None):
    check_in = check_in or today_kst()
    res = Reservation(
        tenant_id=1, customer_name="손님", phone="01012345678",
        check_in_date=check_in, check_in_time="15:00",
        status=status,
        confirmed_at=confirmed_at,
        gender=gender,
        is_long_stay=is_long_stay,
        male_count=male_count,
        female_count=female_count,
    )
    db.add(res)
    db.flush()
    return res


class TestGetTargetsEvent:
    def test_within_hours_since_booking_included(self, db):
        """예약 확정 N시간 이내 → 포함."""
        tpl = _make_template(db)
        sched = _make_event_schedule(db, tpl, hours_since_booking=24)
        # confirmed_at 은 운영 DB 에 naive UTC 로 저장됨 (TIMESTAMP WITHOUT TIME ZONE) —
        # 코드의 cutoff 도 naive 라 테스트도 naive 로 맞춘다.
        confirmed = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        res = _make_reservation(db, check_in=_future(), confirmed_at=confirmed)

        executor = _executor(db)
        targets = executor._get_targets_event(sched)
        assert res.id in [r.id for r in targets]

    def test_outside_hours_since_booking_excluded(self, db):
        """예약 확정 N시간 초과 → 제외."""
        tpl = _make_template(db, key="evt_tpl2")
        sched = _make_event_schedule(db, tpl, hours_since_booking=2)
        old_confirmed = datetime.now(timezone.utc) - timedelta(hours=5)
        res = _make_reservation(db, check_in=today_kst(), confirmed_at=old_confirmed)

        executor = _executor(db)
        targets = executor._get_targets_event(sched)
        assert res.id not in [r.id for r in targets]

    def test_gender_filter_male_only(self, db):
        """gender_filter=male — 남성만 포함 (수동 합성 '남2' 포함, 혼성 제외)."""
        tpl = _make_template(db, key="evt_male")
        sched = _make_event_schedule(db, tpl, gender_filter='male')
        res_male = _make_reservation(db, check_in=_future(), gender='남', male_count=1, female_count=0)
        res_male_composite = _make_reservation(db, check_in=_future(), gender='남2', male_count=2, female_count=None)
        res_female = _make_reservation(db, check_in=_future(), gender='여', male_count=0, female_count=1)
        res_mixed = _make_reservation(db, check_in=_future(), gender='남1여1', male_count=1, female_count=1)

        executor = _executor(db)
        targets = executor._get_targets_event(sched)
        ids = [r.id for r in targets]
        assert res_male.id in ids
        assert res_male_composite.id in ids  # ★ 수동 합성 포맷도 포함
        assert res_female.id not in ids
        assert res_mixed.id not in ids        # 혼성은 제외

    def test_gender_filter_female_only(self, db):
        """gender_filter=female — 여성만 포함 (수동 합성 '여2' 포함, 혼성 제외)."""
        tpl = _make_template(db, key="evt_female")
        sched = _make_event_schedule(db, tpl, gender_filter='female')
        res_male = _make_reservation(db, check_in=_future(), gender='남', male_count=1, female_count=0)
        res_female = _make_reservation(db, check_in=_future(), gender='여', male_count=0, female_count=1)
        res_female_composite = _make_reservation(db, check_in=_future(), gender='여2', male_count=None, female_count=2)
        res_mixed = _make_reservation(db, check_in=_future(), gender='남1여1', male_count=1, female_count=1)

        executor = _executor(db)
        targets = executor._get_targets_event(sched)
        ids = [r.id for r in targets]
        assert res_female.id in ids
        assert res_female_composite.id in ids  # ★ 수동 합성 포맷도 포함
        assert res_male.id not in ids
        assert res_mixed.id not in ids          # 혼성은 제외

    def test_max_checkin_days_filters_far_future(self, db):
        """max_checkin_days — 범위 밖 체크인 제외."""
        from datetime import date
        tpl = _make_template(db, key="evt_maxdays")
        sched = _make_event_schedule(db, tpl, max_checkin_days=3)
        far_future = (date.fromisoformat(today_kst()) + timedelta(days=10)).isoformat()
        res = _make_reservation(db, check_in=far_future)

        executor = _executor(db)
        targets = executor._get_targets_event(sched)
        assert res.id not in [r.id for r in targets]

    def test_no_confirmed_at_excluded_when_hours_filter(self, db):
        """confirmed_at=NULL인 수동 예약 → hours_since_booking 필터 시 제외."""
        tpl = _make_template(db, key="evt_nullconf")
        sched = _make_event_schedule(db, tpl, hours_since_booking=24)
        res = _make_reservation(db, check_in=today_kst(), confirmed_at=None)

        executor = _executor(db)
        targets = executor._get_targets_event(sched)
        assert res.id not in [r.id for r in targets]
