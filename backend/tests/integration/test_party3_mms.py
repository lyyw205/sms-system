"""party3_mms.reconcile_party3_mms 동작 검증.

대상 선정:
  - date 에 투숙/방문 중 (stay_coverage_filter: 첫날/연박 중간일/NULL/당일 포함)
  - status == CONFIRMED
  - 유효 party_type ∈ {'2', '2차만'}
    (ReservationDailyInfo(date).party_type 우선, 없으면 Reservation.party_type)

연박자는 각 밤마다 (reservation_id, date) 쌍으로 칩이 분리 생성되므로,
매일 참여 시 매일 MMS 가 발송된다. 특정 날짜만 미참여로 바꾸려면
해당 날짜의 ReservationDailyInfo.party_type 을 '1'/None 등으로 설정.

stale 칩은 미발송인 경우만 삭제 (이미 발송된 칩은 보존).
"""
from datetime import datetime, timezone, timedelta

from app.db.models import (
    MessageTemplate,
    Reservation,
    ReservationDailyInfo,
    ReservationSmsAssignment,
    ReservationStatus,
    TemplateSchedule,
)
from app.services.party3_mms import reconcile_party3_mms


def _make_template(db):
    t = MessageTemplate(
        tenant_id=1,
        template_key="party3_today_mms",
        name="파티 당일 MMS",
        content="오늘 파티 안내 {{customer_name}}",
        is_active=True,
    )
    db.add(t)
    db.flush()
    return t


def _make_schedule(db, template, active=True):
    s = TemplateSchedule(
        tenant_id=1,
        template_id=template.id,
        schedule_name="party3_today_mms",
        schedule_type="daily",
        hour=23,
        minute=59,
        schedule_category="custom_schedule",
        custom_type="party3_today_mms",
        is_active=active,
    )
    db.add(s)
    db.flush()
    return s


def _make_reservation(db, *, check_in, check_out=None, party_type=None, status=ReservationStatus.CONFIRMED):
    r = Reservation(
        tenant_id=1,
        customer_name="손님",
        phone="01012345678",
        check_in_date=check_in,
        check_out_date=check_out,
        check_in_time="15:00",
        status=status,
        party_type=party_type,
    )
    db.add(r)
    db.flush()
    return r


def _set_daily_party(db, reservation, date, party_type):
    d = ReservationDailyInfo(
        tenant_id=1,
        reservation_id=reservation.id,
        date=date,
        party_type=party_type,
    )
    db.add(d)
    db.flush()
    return d


def _chip_count(db, schedule, date):
    return db.query(ReservationSmsAssignment).filter(
        ReservationSmsAssignment.schedule_id == schedule.id,
        ReservationSmsAssignment.date == date,
    ).count()


class TestParty3MmsReconcile:
    def test_creates_chip_for_party_type_2(self, db):
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        r = _make_reservation(db, check_in=date, party_type="2")

        reconcile_party3_mms(db, date)

        assert _chip_count(db, sch, date) == 1
        chip = db.query(ReservationSmsAssignment).first()
        assert chip.reservation_id == r.id
        assert chip.template_key == "party3_today_mms"
        assert chip.sent_at is None

    def test_creates_chip_for_party_type_2cha_man(self, db):
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        _make_reservation(db, check_in=date, party_type="2차만")

        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 1

    def test_skips_party_type_1(self, db):
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        _make_reservation(db, check_in=date, party_type="1")

        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 0

    def test_skips_party_type_X(self, db):
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        _make_reservation(db, check_in=date, party_type="X")

        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 0

    def test_skips_no_party_type(self, db):
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        _make_reservation(db, check_in=date, party_type=None)

        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 0

    def test_daily_override_wins(self, db):
        """Reservation.party_type='1' 이라도 DailyInfo.party_type='2' 면 대상."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        r = _make_reservation(db, check_in=date, party_type="1")
        _set_daily_party(db, r, date, "2")

        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 1

    def test_daily_override_excludes(self, db):
        """Reservation.party_type='2' 라도 DailyInfo.party_type='X' 면 제외."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        r = _make_reservation(db, check_in=date, party_type="2")
        _set_daily_party(db, r, date, "X")

        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 0

    def test_skips_cancelled(self, db):
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        _make_reservation(db, check_in=date, party_type="2", status=ReservationStatus.CANCELLED)

        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 0

    def test_skips_reservation_not_staying_on_date(self, db):
        """대상 날짜에 투숙 중이 아니면 제외 (check_in 지났고 check_out 도 이미 지남)."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        # 4/21 하룻밤 예약 (체크아웃 NULL) — 4/22에는 해당 없음
        _make_reservation(db, check_in="2026-04-21", party_type="2")

        reconcile_party3_mms(db, "2026-04-22")
        assert _chip_count(db, sch, "2026-04-22") == 0

    def test_creates_chip_for_mid_stay_night(self, db):
        """연박 중간일에도 대상이 된다 (4/22~4/25 예약의 4/23, 4/24 밤)."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        _make_reservation(db, check_in="2026-04-22", check_out="2026-04-25", party_type="2")

        for d in ("2026-04-22", "2026-04-23", "2026-04-24"):
            reconcile_party3_mms(db, d)
            assert _chip_count(db, sch, d) == 1, f"{d} 에 칩이 생성되어야 함"

        # 4/25 는 체크아웃일 — 제외
        reconcile_party3_mms(db, "2026-04-25")
        assert _chip_count(db, sch, "2026-04-25") == 0

    def test_skips_mid_stay_night_when_daily_override_non_party3(self, db):
        """연박 중간일에 ReservationDailyInfo.party_type 을 '1' 로 덮으면 그 날만 제외."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        r = _make_reservation(db, check_in="2026-04-22", check_out="2026-04-25", party_type="2")

        # 4/23 만 '1' 로 override (1차만 참여)
        _set_daily_party(db, r, "2026-04-23", "1")

        reconcile_party3_mms(db, "2026-04-22")
        reconcile_party3_mms(db, "2026-04-23")
        reconcile_party3_mms(db, "2026-04-24")

        assert _chip_count(db, sch, "2026-04-22") == 1
        assert _chip_count(db, sch, "2026-04-23") == 0  # override 로 제외
        assert _chip_count(db, sch, "2026-04-24") == 1

    def test_creates_chip_for_same_day_checkin_checkout(self, db):
        """당일 체크인/체크아웃 (party/unstable 류) 도 대상."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        _make_reservation(db, check_in=date, check_out=date, party_type="2차만")

        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 1

    def test_no_active_schedule_creates_nothing(self, db):
        tpl = _make_template(db)
        _make_schedule(db, tpl, active=False)
        date = "2026-04-22"
        _make_reservation(db, check_in=date, party_type="2")

        reconcile_party3_mms(db, date)
        assert db.query(ReservationSmsAssignment).count() == 0

    def test_deletes_stale_unsent_chip(self, db):
        """party_type 변경으로 더이상 대상 아니면 미발송 칩 삭제."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        r = _make_reservation(db, check_in=date, party_type="2")

        # 첫 reconcile → 칩 생성
        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 1

        # party_type 을 '1' 로 변경 (daily override)
        _set_daily_party(db, r, date, "1")

        # 재조정 → 미발송 칩 삭제
        reconcile_party3_mms(db, date)
        assert _chip_count(db, sch, date) == 0

    def test_preserves_sent_chip(self, db):
        """이미 발송된 칩은 조건 불만족이어도 보존."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        r = _make_reservation(db, check_in=date, party_type="2")

        reconcile_party3_mms(db, date)
        chip = db.query(ReservationSmsAssignment).first()
        chip.sent_at = datetime.now(timezone.utc)
        db.flush()

        # party_type 변경 후 재조정
        _set_daily_party(db, r, date, "1")
        reconcile_party3_mms(db, date)

        # 발송된 칩은 남아있어야 함
        assert _chip_count(db, sch, date) == 1

    def test_idempotent(self, db):
        """동일 조건으로 여러 번 호출해도 칩이 중복 생성되지 않음."""
        tpl = _make_template(db)
        sch = _make_schedule(db, tpl)
        date = "2026-04-22"
        _make_reservation(db, check_in=date, party_type="2")

        reconcile_party3_mms(db, date)
        reconcile_party3_mms(db, date)
        reconcile_party3_mms(db, date)

        assert _chip_count(db, sch, date) == 1
