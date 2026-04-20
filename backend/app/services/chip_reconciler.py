"""
칩(ReservationSmsAssignment) reconcile 모듈.

칩 = "이 예약자에게 / 이 날짜에 / 이 템플릿 SMS를 보낼 예정" 이라는 기록.

두 가지 reconcile 경로:
  - reservation-centric: 1 예약 × N 스케줄 × M 날짜 (예약 생성/수정/배정 시)
  - schedule-centric:    1 스케줄 × N 예약 × M 날짜 (스케줄 생성/수정/실행 시)

핵심 로직:
  1. get_schedule_dates(schedule, reservation) → 칩이 필요한 날짜 목록
  2. _reservation_matches_schedule(db, schedule, reservation, date) → 그 날 필터 통과?
  3. _sync_chips(expected, existing) → diff: 없는 칩 생성, 불필요 칩 삭제

칩 보호: assigned_by='manual'/'excluded' 또는 sent_at 있으면 삭제 안 됨.
"""
import logging
from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.db.models import (
    Reservation,
    ReservationSmsAssignment,
    ReservationStatus,
    TemplateSchedule,
)
from app.config import today_kst
from app.diag_logger import diag
from app.services.filters import apply_structural_filters
from app.services.schedule_utils import get_schedule_dates, resolve_target_date

logger = logging.getLogger(__name__)

# Chip protection rules (unified)
_PROTECTED_ASSIGNED_BY = {'manual', 'excluded'}


def reconcile_chips_for_reservation(
    db: Session,
    reservation_id: int,
    schedules: Optional[list] = None,
) -> None:
    """Reconcile chips for a single reservation against all active schedules.

    For each schedule, checks if the reservation matches the schedule's
    structural filters. Creates missing chips, deletes stale chips.

    Does NOT commit — caller owns the transaction.
    """
    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id
    ).first()
    if not reservation:
        return

    diag("reconcile_chips_for_reservation.enter", level="verbose", res_id=reservation_id)

    # 취소된 예약: 기존 미발송 칩만 정리하고 리턴 (새 칩 생성 안 함)
    if reservation.status == ReservationStatus.CANCELLED:
        existing = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == reservation_id,
            ReservationSmsAssignment.sent_at.is_(None),
            ~ReservationSmsAssignment.assigned_by.in_(_PROTECTED_ASSIGNED_BY),
        ).all()
        for a in existing:
            db.delete(a)
        diag(
            "reconcile_chips_for_reservation.exit",
            level="verbose",
            res_id=reservation_id,
            cancelled_cleanup=len(existing),
        )
        return

    if schedules is None:
        schedules = db.query(TemplateSchedule).filter(
            TemplateSchedule.is_active == True
        ).all()

    # Compute expected (template_key, date) pairs with schedule_id tracking
    expected_pairs: Set[Tuple[str, str]] = set()
    expected_schedule_map: dict = {}  # (template_key, date) -> schedule_id
    for schedule in schedules:
        if not schedule.template or not schedule.template.is_active:
            continue
        # Event schedules cannot have static chips
        if (schedule.schedule_category or 'standard') in ('event', 'custom_schedule'):
            continue

        template_key = schedule.template.template_key
        dates = get_schedule_dates(schedule, reservation)
        for d in dates:
            if _reservation_matches_schedule(db, schedule, reservation, d):
                expected_pairs.add((template_key, d))
                if (template_key, d) not in expected_schedule_map:
                    expected_schedule_map[(template_key, d)] = schedule.id

    # Get current chips for this reservation (custom_schedule 소속 칩 제외)
    custom_schedule_ids = {s.id for s in schedules if (s.schedule_category or 'standard') == 'custom_schedule'}
    all_existing = db.query(ReservationSmsAssignment).filter(
        ReservationSmsAssignment.reservation_id == reservation_id,
    ).all()
    existing = [a for a in all_existing if a.schedule_id not in custom_schedule_ids]

    created = _sync_chips(db, expected_pairs, existing, reservation_id=reservation_id, schedule_map=expected_schedule_map)

    diag(
        "reconcile_chips_for_reservation.exit",
        level="verbose",
        res_id=reservation_id,
        expected=len(expected_pairs),
        existing=len(existing),
        created=created,
    )


def reconcile_chips_for_schedule(
    db: Session,
    schedule: TemplateSchedule,
) -> int:
    """Reconcile chips for a single schedule against all matching reservations.

    Finds candidate reservations (date-independent filters), then checks
    date-dependent filters per-date for each candidate.

    Does NOT commit — caller owns the transaction.

    Returns:
        Number of new chips created.
    """
    if not schedule.template:
        return 0
    template_key = schedule.template.template_key

    diag(
        "reconcile_chips_for_schedule.enter",
        level="verbose",
        schedule_id=schedule.id,
        template_key=template_key,
    )

    # 비활성 스케줄/템플릿/이벤트: 자기가 만든 칩만 삭제
    if not schedule.template.is_active or not schedule.is_active or (schedule.schedule_category or 'standard') in ('event', 'custom_schedule'):
        existing = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.template_key == template_key,
            ReservationSmsAssignment.schedule_id == schedule.id,
        ).all()
        created = _sync_chips_for_schedule(db, set(), existing, template_key, schedule.id)
        diag(
            "reconcile_chips_for_schedule.exit",
            level="verbose",
            schedule_id=schedule.id,
            template_key=template_key,
            inactive_cleanup=True,
            existing=len(existing),
            created=created,
        )
        return created

    # 활성: 후보 예약 조회 (날짜 무관 필터만) + per-date 필터링
    target_date = resolve_target_date(schedule.date_target) if schedule.date_target else today_kst()
    candidates = _get_candidate_reservations(db, schedule, target_date)

    # scope_dates: 후보 예약의 전체 스케줄 날짜 범위 (필터링 전)
    # → stale 칩 삭제 누락 방지
    scope_dates: set = {target_date}
    expected_pairs: Set[Tuple[int, str]] = set()

    for reservation in candidates:
        dates = get_schedule_dates(schedule, reservation)
        scope_dates.update(dates)  # 필터링 전에 scope에 추가
        for d in dates:
            if _reservation_matches_schedule(db, schedule, reservation, d):
                expected_pairs.add((reservation.id, d))

    # scope_dates 범위 내 자기 칩만 diff 대상
    existing = db.query(ReservationSmsAssignment).filter(
        ReservationSmsAssignment.template_key == template_key,
        ReservationSmsAssignment.schedule_id == schedule.id,
        ReservationSmsAssignment.date.in_(scope_dates),
    ).all()

    created = _sync_chips_for_schedule(db, expected_pairs, existing, template_key, schedule.id)

    diag(
        "reconcile_chips_for_schedule.exit",
        level="verbose",
        schedule_id=schedule.id,
        template_key=template_key,
        candidates=len(candidates),
        expected=len(expected_pairs),
        existing=len(existing),
        created=created,
    )

    return created


def _reservation_matches_schedule(
    db: Session,
    schedule: TemplateSchedule,
    reservation: Reservation,
    target_date: str,
) -> bool:
    """Check if a reservation matches a schedule's structural filters for a specific date.

    For checkout dates (no RoomAssignment), falls back to check_out - 1 day
    for building/room filters.
    """
    from datetime import datetime, timedelta

    # checkout일 fallback: checkout일에는 RoomAssignment 없으므로
    # check_out - 1일의 배정을 기준으로 체크
    effective_date = target_date
    if reservation.check_out_date == target_date:
        prev_day = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        if prev_day >= (reservation.check_in_date or target_date):
            effective_date = prev_day

    query = db.query(Reservation).filter(Reservation.id == reservation.id)
    query = apply_structural_filters(db, query, schedule, effective_date)
    return query.first() is not None


def _get_candidate_reservations(
    db: Session,
    schedule: TemplateSchedule,
    target_date: str,
) -> List[Reservation]:
    """Get candidate reservations using only date-independent filters.

    Applies date range filter + assignment/gender/naver_room_type only.
    Building/room/column_match(party_type, notes) are deferred to per-date check.
    """
    query = db.query(Reservation).filter(
        Reservation.status == ReservationStatus.CONFIRMED,
    )

    # Date range: include reservations active on target_date
    date_target_val = schedule.date_target
    if date_target_val and date_target_val.endswith('_checkout'):
        query = query.filter(
            Reservation.check_out_date.isnot(None),
            Reservation.check_out_date == target_date,
        )
    else:
        target_mode = schedule.target_mode or 'once'
        if target_mode in ('daily', 'last_day'):
            query = query.filter(
                or_(
                    and_(
                        Reservation.check_in_date <= target_date,
                        Reservation.check_out_date > target_date,
                    ),
                    and_(
                        Reservation.check_in_date == target_date,
                        Reservation.check_out_date.is_(None),
                    ),
                )
            )
        else:
            query = query.filter(Reservation.check_in_date == target_date)

    # 날짜 무관 필터만 적용 (assignment, gender, naver_room_type 등)
    query = apply_structural_filters(db, query, schedule, target_date, only_date_independent=True)

    return query.all()


def _sync_chips(
    db: Session,
    expected_pairs: Set[Tuple[str, str]],
    existing: list,
    reservation_id: int,
    schedule_map: Optional[dict] = None,
) -> int:
    """Diff-based chip sync for a single reservation.

    expected_pairs: set of (template_key, date)
    existing: list of ReservationSmsAssignment for this reservation
    schedule_map: optional dict of (template_key, date) -> schedule_id

    Returns number of chips created.
    """
    existing_pairs = {(a.template_key, a.date) for a in existing}
    excluded_pairs = {(a.template_key, a.date) for a in existing if a.assigned_by == 'excluded'}

    created = 0

    # Create missing chips (skip excluded)
    for (key, d) in expected_pairs:
        if (key, d) not in existing_pairs and (key, d) not in excluded_pairs:
            db.add(ReservationSmsAssignment(
                reservation_id=reservation_id,
                template_key=key,
                date=d,
                assigned_by='auto',
                sent_at=None,
                schedule_id=schedule_map.get((key, d)) if schedule_map else None,
            ))
            created += 1

    # Delete stale chips (only unprotected, skip failed)
    for a in existing:
        if (a.template_key, a.date) not in expected_pairs:
            if a.sent_at is None and a.assigned_by not in _PROTECTED_ASSIGNED_BY and a.send_status != 'failed':
                db.delete(a)

    return created


def _sync_chips_for_schedule(
    db: Session,
    expected_pairs: Set[Tuple[int, str]],
    existing: list,
    template_key: str,
    schedule_id: Optional[int] = None,
) -> int:
    """Diff-based chip sync for a single schedule (across all reservations).

    expected_pairs: set of (reservation_id, date)
    existing: list of ReservationSmsAssignment for this schedule
    schedule_id: the schedule that owns these chips

    Returns number of chips created.
    """
    existing_pairs = {(a.reservation_id, a.date) for a in existing}
    excluded_pairs = {(a.reservation_id, a.date) for a in existing if a.assigned_by == 'excluded'}

    created = 0

    # Create missing chips (skip excluded)
    for (res_id, d) in expected_pairs:
        if (res_id, d) not in existing_pairs and (res_id, d) not in excluded_pairs:
            # Check if another schedule already created a chip for same unique key
            already_exists = db.query(ReservationSmsAssignment).filter(
                ReservationSmsAssignment.reservation_id == res_id,
                ReservationSmsAssignment.template_key == template_key,
                ReservationSmsAssignment.date == d,
            ).first()
            if not already_exists:
                db.add(ReservationSmsAssignment(
                    reservation_id=res_id,
                    template_key=template_key,
                    date=d,
                    assigned_by='schedule',
                    sent_at=None,
                    schedule_id=schedule_id,
                ))
                created += 1

    # Delete stale chips (only unprotected, skip failed)
    for a in existing:
        if (a.reservation_id, a.date) not in expected_pairs:
            if a.sent_at is None and a.assigned_by not in _PROTECTED_ASSIGNED_BY and a.send_status != 'failed':
                db.delete(a)

    return created
