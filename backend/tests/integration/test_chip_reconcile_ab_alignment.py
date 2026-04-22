"""A/B 경로 일치성 회귀 테스트.

대상 집합(칩 생성 대상 예약)이 두 경로에서 동일하게 결정되는지 확인:
  A 경로: TemplateScheduleExecutor._get_targets_standard()  (발송 실행 시)
  B 경로: reconcile_chips_for_schedule() / _get_candidate_reservations()  (칩 동기화 시)

커버 범위:
  A-case: 오늘 기준 과거 10일 체크인 → safety guard 로 양쪽에서 제외
  B-case: 오늘 +5일 체크인 → safety guard(today+1 상한) 로 양쪽에서 제외
  C-case: 오늘 체크인 → safety guard 범위 내 → 정상 칩 생성
  D-case: is_long_stay=True + stay_filter='exclude' → 양쪽에서 제외
  E-case: is_long_stay=False + stay_filter='exclude' → 포함
  F-case: is_long_stay=True + stay_filter 없음 → 포함
  G-case: A/B 일치성 통합 — 같은 스케줄에 대해 id 집합이 동일
"""
import pytest
from datetime import date, timedelta

from app.db.models import (
    Reservation,
    ReservationStatus,
    ReservationSmsAssignment,
    MessageTemplate,
    TemplateSchedule,
)
from app.services.chip_reconciler import reconcile_chips_for_schedule
from app.scheduler.template_scheduler import TemplateScheduleExecutor
from app.config import today_kst, today_kst_date


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _today() -> str:
    return today_kst()


def _date_offset(days: int) -> str:
    return (today_kst_date() + timedelta(days=days)).strftime('%Y-%m-%d')


def _make_template(db, key="ab_tpl"):
    tpl = MessageTemplate(
        tenant_id=1, template_key=key, name="AB Test", content="hello", is_active=True,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _make_schedule(db, template, stay_filter=None, target_mode='first_night', date_target='today'):
    filters = {}
    if stay_filter:
        filters['stay_filter'] = stay_filter
    sched = TemplateSchedule(
        tenant_id=1,
        template_id=template.id,
        schedule_name="ab_test",
        schedule_type="daily",
        hour=9,
        minute=0,
        target_mode=target_mode,
        date_target=date_target,
        stay_filter=stay_filter,
        is_active=True,
    )
    db.add(sched)
    db.flush()
    return sched


def _make_reservation(db, check_in: str, is_long_stay: bool = False,
                      status=ReservationStatus.CONFIRMED):
    res = Reservation(
        tenant_id=1,
        customer_name="테스트손님",
        phone="01099999999",
        check_in_date=check_in,
        check_in_time="15:00",
        status=status,
        is_long_stay=is_long_stay,
    )
    db.add(res)
    db.flush()
    return res


def _get_chip_reservation_ids(db, sched):
    """reconcile 후 해당 스케줄이 만든 칩의 reservation_id 집합."""
    chips = db.query(ReservationSmsAssignment).filter(
        ReservationSmsAssignment.schedule_id == sched.id,
        ReservationSmsAssignment.sent_at.is_(None),
    ).all()
    return {c.reservation_id for c in chips}


def _executor(db):
    return TemplateScheduleExecutor(db, tenant=None)


# ---------------------------------------------------------------------------
# A-case: safety guard — 과거 10일 체크인 → 제외
# ---------------------------------------------------------------------------

class TestSafetyGuardPast:
    def test_A_past_checkin_excluded_from_chips(self, db):
        """과거 10일 체크인 예약은 safety guard 로 칩이 생성되지 않는다."""
        tpl = _make_template(db, key="a_past")
        sched = _make_schedule(db, tpl)
        past_checkin = _date_offset(-10)
        res = _make_reservation(db, check_in=past_checkin)

        created = reconcile_chips_for_schedule(db, sched)
        db.flush()

        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()
        assert len(chips) == 0, (
            f"check_in={past_checkin} 예약은 safety guard(today-7) 밖이므로 칩이 생성되면 안 됨"
        )


# ---------------------------------------------------------------------------
# B-case: safety guard — 미래 +5일 체크인 → 제외
# ---------------------------------------------------------------------------

class TestSafetyGuardFuture:
    def test_B_future_checkin_excluded_from_chips(self, db):
        """오늘 +5일 체크인 예약은 safety guard(today+1 상한) 로 칩이 생성되지 않는다."""
        tpl = _make_template(db, key="b_future")
        sched = _make_schedule(db, tpl)
        future_checkin = _date_offset(5)
        res = _make_reservation(db, check_in=future_checkin)

        created = reconcile_chips_for_schedule(db, sched)
        db.flush()

        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()
        assert len(chips) == 0, (
            f"check_in={future_checkin} 예약은 safety guard(today+1) 상한 밖이므로 칩이 생성되면 안 됨"
        )


# ---------------------------------------------------------------------------
# C-case: 오늘 체크인 → 정상 칩 생성
# ---------------------------------------------------------------------------

class TestSafetyGuardToday:
    def test_C_today_checkin_creates_chip(self, db):
        """오늘 체크인 예약은 safety guard 범위 내이므로 칩이 생성된다."""
        tpl = _make_template(db, key="c_today")
        sched = _make_schedule(db, tpl)
        res = _make_reservation(db, check_in=_today())

        created = reconcile_chips_for_schedule(db, sched)
        db.flush()

        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()
        assert len(chips) >= 1, (
            f"check_in={_today()} 예약은 safety guard 범위 내이므로 칩이 생성되어야 함"
        )


# ---------------------------------------------------------------------------
# D-case: stay_filter='exclude' + is_long_stay=True → 칩 생성 안 됨
# ---------------------------------------------------------------------------

class TestStayFilterExcludeLongStay:
    def test_D_long_stay_excluded_when_stay_filter_exclude(self, db):
        """is_long_stay=True 예약은 stay_filter='exclude' 스케줄에서 칩이 만들어지지 않는다."""
        tpl = _make_template(db, key="d_long")
        sched = _make_schedule(db, tpl, stay_filter='exclude')
        res = _make_reservation(db, check_in=_today(), is_long_stay=True)

        created = reconcile_chips_for_schedule(db, sched)
        db.flush()

        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()
        assert len(chips) == 0, (
            "is_long_stay=True 예약은 stay_filter='exclude' 일 때 칩이 생성되면 안 됨"
        )


# ---------------------------------------------------------------------------
# E-case: stay_filter='exclude' + is_long_stay=False → 정상 칩 생성
# ---------------------------------------------------------------------------

class TestStayFilterExcludeShortStay:
    def test_E_short_stay_included_when_stay_filter_exclude(self, db):
        """is_long_stay=False 예약은 stay_filter='exclude' 스케줄에서도 칩이 생성된다."""
        tpl = _make_template(db, key="e_short")
        sched = _make_schedule(db, tpl, stay_filter='exclude')
        res = _make_reservation(db, check_in=_today(), is_long_stay=False)

        created = reconcile_chips_for_schedule(db, sched)
        db.flush()

        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()
        assert len(chips) >= 1, (
            "is_long_stay=False 예약은 stay_filter='exclude' 여도 칩이 생성되어야 함"
        )


# ---------------------------------------------------------------------------
# F-case: stay_filter 없음 + is_long_stay=True → 정상 칩 생성
# ---------------------------------------------------------------------------

class TestStayFilterNone:
    def test_F_long_stay_included_when_no_stay_filter(self, db):
        """stay_filter 미설정 스케줄에서는 is_long_stay=True 예약도 칩이 생성된다."""
        tpl = _make_template(db, key="f_no_filter")
        sched = _make_schedule(db, tpl, stay_filter=None)
        res = _make_reservation(db, check_in=_today(), is_long_stay=True)

        created = reconcile_chips_for_schedule(db, sched)
        db.flush()

        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()
        assert len(chips) >= 1, (
            "stay_filter 없는 스케줄에서는 is_long_stay=True 예약도 칩이 생성되어야 함"
        )


# ---------------------------------------------------------------------------
# G-case: A/B 일치성 통합
# ---------------------------------------------------------------------------

class TestABPathAlignment:
    """_get_targets_standard (A) 와 reconcile_chips_for_schedule (B) 의 대상 id 집합 일치 검증."""

    def _targets_a(self, db, sched) -> set:
        executor = _executor(db)
        targets = executor._get_targets_standard(sched, exclude_sent=False)
        return {r.id for r in targets}

    def _targets_b(self, db, sched) -> set:
        reconcile_chips_for_schedule(db, sched)
        db.flush()
        return _get_chip_reservation_ids(db, sched)

    def test_G_safety_guard_past_excluded_on_both_paths(self, db):
        """safety guard 밖 과거 예약이 A경로(발송 대상)와 B경로(칩) 모두에서 제외된다."""
        tpl = _make_template(db, key="g_past_both")
        sched = _make_schedule(db, tpl)
        res_past = _make_reservation(db, check_in=_date_offset(-10))
        res_today = _make_reservation(db, check_in=_today())

        ids_a = self._targets_a(db, sched)
        ids_b = self._targets_b(db, sched)

        # 과거 예약은 양쪽에서 제외
        assert res_past.id not in ids_a, "A경로: 과거 10일 예약은 발송 대상에서 제외되어야 함"
        assert res_past.id not in ids_b, "B경로: 과거 10일 예약은 칩 대상에서 제외되어야 함"

        # 오늘 예약은 양쪽에서 포함
        assert res_today.id in ids_a, "A경로: 오늘 체크인 예약은 발송 대상에 포함되어야 함"
        assert res_today.id in ids_b, "B경로: 오늘 체크인 예약은 칩 대상에 포함되어야 함"

    def test_G_long_stay_excluded_on_both_paths_when_stay_filter(self, db):
        """stay_filter='exclude' 시 연박자가 A경로와 B경로 모두에서 동일하게 제외된다."""
        tpl = _make_template(db, key="g_stay_both")
        sched = _make_schedule(db, tpl, stay_filter='exclude')
        res_long = _make_reservation(db, check_in=_today(), is_long_stay=True)
        res_short = _make_reservation(db, check_in=_today(), is_long_stay=False)

        ids_a = self._targets_a(db, sched)
        ids_b = self._targets_b(db, sched)

        # 연박자는 양쪽에서 제외
        assert res_long.id not in ids_a, "A경로: 연박자는 stay_filter=exclude 시 제외되어야 함"
        assert res_long.id not in ids_b, "B경로: 연박자는 stay_filter=exclude 시 제외되어야 함"

        # 1박자는 양쪽에서 포함
        assert res_short.id in ids_a, "A경로: 1박자는 stay_filter=exclude 여도 포함되어야 함"
        assert res_short.id in ids_b, "B경로: 1박자는 stay_filter=exclude 여도 포함되어야 함"

    def test_G_future_checkin_excluded_on_both_paths(self, db):
        """safety guard 상한(today+1) 밖 미래 예약이 A/B 경로 모두에서 제외된다."""
        tpl = _make_template(db, key="g_future_both")
        sched = _make_schedule(db, tpl)
        res_future = _make_reservation(db, check_in=_date_offset(5))

        ids_a = self._targets_a(db, sched)
        ids_b = self._targets_b(db, sched)

        assert res_future.id not in ids_a, "A경로: +5일 미래 예약은 발송 대상에서 제외되어야 함"
        assert res_future.id not in ids_b, "B경로: +5일 미래 예약은 칩 대상에서 제외되어야 함"
