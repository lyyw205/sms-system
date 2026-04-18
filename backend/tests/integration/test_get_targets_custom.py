"""custom_schedule이 standard 발송 경로로 합류한 뒤의 동작 회귀 테스트."""
from datetime import datetime, timezone, timedelta

from app.config import today_kst, today_kst_date
from app.db.models import (
    MessageTemplate,
    Reservation,
    ReservationSmsAssignment,
    ReservationStatus,
    TemplateSchedule,
)
from app.scheduler.template_scheduler import TemplateScheduleExecutor


def _executor(db):
    return TemplateScheduleExecutor(db, tenant=None)


def _make_template(db, key="add_one_person"):
    tpl = MessageTemplate(
        tenant_id=1, template_key=key, name="추가요금", content="hello", is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _make_custom_schedule(db, template, custom_type="surcharge_1",
                          date_target=None, target_mode=None, exclude_sent=None, once_per_stay=None):
    """custom_schedule — NULL 필드 기본값에 의존하도록 미설정 가능."""
    kwargs = dict(
        tenant_id=1,
        template_id=template.id,
        schedule_name=f"custom {custom_type}",
        schedule_type="daily",
        hour=13,
        minute=25,
        schedule_category="custom_schedule",
        custom_type=custom_type,
        is_active=True,
    )
    if date_target is not None:
        kwargs["date_target"] = date_target
    if target_mode is not None:
        kwargs["target_mode"] = target_mode
    if exclude_sent is not None:
        kwargs["exclude_sent"] = exclude_sent
    if once_per_stay is not None:
        kwargs["once_per_stay"] = once_per_stay
    sched = TemplateSchedule(**kwargs)
    db.add(sched)
    db.flush()
    return sched


def _make_reservation(db, *, check_in=None, check_out=None, is_long_stay=False, stay_group_id=None, name="손님"):
    check_in = check_in or today_kst()
    res = Reservation(
        tenant_id=1,
        customer_name=name,
        phone="01012345678",
        check_in_date=check_in,
        check_in_time="15:00",
        check_out_date=check_out,
        status=ReservationStatus.CONFIRMED,
        is_long_stay=is_long_stay,
        stay_group_id=stay_group_id,
    )
    db.add(res)
    db.flush()
    return res


def _make_chip(db, reservation, schedule, *, date=None, sent_at=None, send_status=None):
    chip = ReservationSmsAssignment(
        tenant_id=1,
        reservation_id=reservation.id,
        template_key=schedule.template.template_key,
        date=date or today_kst(),
        assigned_by="auto",
        schedule_id=schedule.id,
        sent_at=sent_at,
        send_status=send_status,
    )
    db.add(chip)
    db.flush()
    return chip


class TestCustomEligibility:
    def test_no_chip_no_target(self, db):
        """pending 칩이 없으면 custom 스케줄 대상 없음."""
        tpl = _make_template(db)
        sched = _make_custom_schedule(db, tpl)
        _make_reservation(db, check_in=today_kst())

        targets = _executor(db).get_targets(sched)
        assert targets == []

    def test_pending_chip_today_included(self, db):
        """오늘 date의 pending 칩이 있으면 대상 포함."""
        tpl = _make_template(db)
        sched = _make_custom_schedule(db, tpl)
        res = _make_reservation(db, check_in=today_kst(), check_out=None)
        _make_chip(db, res, sched, date=today_kst())

        targets = _executor(db).get_targets(sched)
        assert [t.id for t in targets] == [res.id]

    def test_past_dated_chip_excluded(self, db):
        """과거 날짜 잔여 칩은 오늘 발송 대상에서 제외 — 패턴 B 차단."""
        tpl = _make_template(db)
        sched = _make_custom_schedule(db, tpl)
        res = _make_reservation(db, check_in=today_kst())
        past = (today_kst_date() - timedelta(days=2)).strftime("%Y-%m-%d")
        _make_chip(db, res, sched, date=past)

        targets = _executor(db).get_targets(sched)
        assert targets == []

    def test_sent_chip_excluded(self, db):
        """sent_at 이 설정된 칩은 후보에서 제외."""
        tpl = _make_template(db)
        sched = _make_custom_schedule(db, tpl)
        res = _make_reservation(db, check_in=today_kst())
        _make_chip(db, res, sched, date=today_kst(), sent_at=datetime.now(timezone.utc))

        targets = _executor(db).get_targets(sched)
        assert targets == []

    def test_failed_chip_excluded(self, db):
        """send_status='failed' 칩은 후보에서 제외 — 재발송 금지."""
        tpl = _make_template(db)
        sched = _make_custom_schedule(db, tpl)
        res = _make_reservation(db, check_in=today_kst())
        _make_chip(db, res, sched, date=today_kst(), send_status="failed")

        targets = _executor(db).get_targets(sched)
        assert targets == []


class TestCustomLongStayDeduplication:
    def test_long_stay_blocked_after_first_send(self, db):
        """연박자: 첫날 발송 후 둘째 날 pending 칩이 있어도 once_per_stay로 차단 — 패턴 A."""
        tpl = _make_template(db)
        sched = _make_custom_schedule(db, tpl)

        today = today_kst_date().strftime("%Y-%m-%d")
        checkout = (today_kst_date() + timedelta(days=2)).strftime("%Y-%m-%d")

        res = _make_reservation(
            db,
            check_in=today,
            check_out=checkout,
            is_long_stay=True,
        )

        # 1일차에 이미 발송된 기록 + 오늘(2일차) pending 칩
        past = (today_kst_date() - timedelta(days=1)).strftime("%Y-%m-%d")
        _make_chip(db, res, sched, date=past, sent_at=datetime.now(timezone.utc))
        _make_chip(db, res, sched, date=today)

        targets = _executor(db).get_targets(sched)
        assert targets == [], "연박자에게 같은 템플릿을 하루 뒤 또 보내면 안 됨"

    def test_single_night_still_sends(self, db):
        """단박 예약은 once_per_stay 영향 없이 정상 발송."""
        tpl = _make_template(db)
        sched = _make_custom_schedule(db, tpl)

        today = today_kst_date().strftime("%Y-%m-%d")
        checkout = (today_kst_date() + timedelta(days=1)).strftime("%Y-%m-%d")

        res = _make_reservation(
            db,
            check_in=today,
            check_out=checkout,
            is_long_stay=False,
        )
        _make_chip(db, res, sched, date=today)

        targets = _executor(db).get_targets(sched)
        assert [t.id for t in targets] == [res.id]


class TestCustomDefaultCoercion:
    def test_null_date_target_defaults_to_today(self, db):
        """custom_schedule 의 date_target 이 NULL 이어도 오늘 칩 기준으로 동작."""
        tpl = _make_template(db)
        # date_target 미지정
        sched = _make_custom_schedule(db, tpl, date_target=None, target_mode=None)
        res = _make_reservation(db, check_in=today_kst(), check_out=None)
        _make_chip(db, res, sched, date=today_kst())

        targets = _executor(db).get_targets(sched)
        assert [t.id for t in targets] == [res.id]

    def test_custom_schedule_with_date_target_tomorrow(self, db):
        """custom 스케줄이 date_target='tomorrow' 로 명시 설정되면 내일 칩만 eligibility 통과."""
        tpl = _make_template(db)
        sched = _make_custom_schedule(db, tpl, date_target='tomorrow', target_mode='daily')

        tomorrow = (today_kst_date() + timedelta(days=1)).strftime("%Y-%m-%d")
        checkout = (today_kst_date() + timedelta(days=2)).strftime("%Y-%m-%d")

        res = _make_reservation(
            db,
            check_in=tomorrow,
            check_out=checkout,
        )
        # 오늘 칩 (noise) + 내일 칩 (정답)
        _make_chip(db, res, sched, date=today_kst())
        _make_chip(db, res, sched, date=tomorrow)

        targets = _executor(db).get_targets(sched)
        # 내일 칩 기준으로 예약 1건이 잡혀야 함 (오늘 칩은 date_target 이 내일이라 탈락)
        assert [t.id for t in targets] == [res.id]


class TestStandardRegression:
    """custom 주입이 standard 경로에 영향 없음을 확인하는 회귀 테스트."""

    def test_standard_ignored_by_eligibility_filter(self, db):
        """category='standard' 스케줄은 칩 존재 여부와 무관하게 동작."""
        tpl = _make_template(db, key="std_only")
        sched = TemplateSchedule(
            tenant_id=1,
            template_id=tpl.id,
            schedule_name="std",
            schedule_type="daily",
            hour=9,
            minute=0,
            target_mode="once",
            date_target="today",
            schedule_category="standard",
            is_active=True,
        )
        db.add(sched)
        db.flush()

        res = _make_reservation(db, check_in=today_kst())
        # 의도적으로 칩을 만들지 않음 → custom 경로였다면 탈락
        targets = _executor(db).get_targets(sched)
        assert res.id in [t.id for t in targets]

    def test_null_category_treated_as_standard(self, db):
        """schedule_category NULL 도 standard 로 간주 — 기존 동작 유지."""
        tpl = _make_template(db, key="null_cat")
        sched = TemplateSchedule(
            tenant_id=1,
            template_id=tpl.id,
            schedule_name="nullcat",
            schedule_type="daily",
            hour=9,
            minute=0,
            target_mode="once",
            date_target="today",
            is_active=True,
        )
        db.add(sched)
        db.flush()

        res = _make_reservation(db, check_in=today_kst())
        targets = _executor(db).get_targets(sched)
        assert res.id in [t.id for t in targets]
