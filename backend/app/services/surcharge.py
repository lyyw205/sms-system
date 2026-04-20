"""
surcharge.py — 초과 인원 추가요금 SMS 칩 자동 조정 서비스

예약 인원이 객실 기본 정원(base_capacity)을 초과할 경우,
초과 인원 수별로 추가요금 템플릿 칩(예: "추2", "추4")을
ReservationSmsAssignment에 자동으로 생성/삭제합니다.

각 초과 단위는 별도 custom_type의 스케줄로 관리됩니다:
  surcharge_1 → 1인 초과 → "추2" 템플릿
  surcharge_2 → 2인 초과 → "추4" 템플릿
  surcharge_3 → 3인 초과 → "추6" 템플릿
  surcharge_4 → 4인 초과 → "추8" 템플릿

칩은 assigned_by='auto', schedule_id=해당 스케줄 ID로 생성되어
standard 칩과 동일한 생명주기를 가집니다.
"""
import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.db.models import (
    Reservation,
    Room,
    RoomAssignment,
    ReservationSmsAssignment,
    MessageTemplate,
    TemplateSchedule,
)
from app.db.tenant_context import current_tenant_id
from app.diag_logger import diag

logger = logging.getLogger(__name__)

# 지원하는 초과 인원 단위 (1~4인)
SURCHARGE_LEVELS = [1, 2, 3, 4]


def _custom_type_for_level(level: int) -> str:
    """초과 인원 단위에 해당하는 custom_type 값."""
    return f"surcharge_{level}"


def _find_schedule(db: Session, custom_type: str) -> Optional[TemplateSchedule]:
    """해당 custom_type의 활성 custom_schedule을 조회합니다."""
    return db.query(TemplateSchedule).filter(
        TemplateSchedule.schedule_category == 'custom_schedule',
        TemplateSchedule.custom_type == custom_type,
        TemplateSchedule.is_active == True,
    ).first()


def reconcile_surcharge(
    db: Session,
    reservation_id: int,
    date: str,
    room_id: Optional[int] = None,
) -> None:
    """
    예약-날짜 기준으로 초과 인원 추가요금 SMS 칩을 재조정합니다.

    초과 인원에 해당하는 레벨의 칩만 생성하고, 나머지 레벨의 칩은 삭제합니다.
    예: 2인 초과 → surcharge_2 스케줄의 칩 생성, surcharge_1/3/4 칩 삭제
    """
    diag("surcharge.reconcile.enter", level="verbose", res_id=reservation_id, date=date)
    try:
        # 1. RoomAssignment 조회
        query = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == reservation_id,
            RoomAssignment.date == date,
        )
        if room_id is not None:
            query = query.filter(RoomAssignment.room_id == room_id)

        assignment = query.first()
        if assignment is None:
            # 배정 없음 → 모든 surcharge 칩 삭제
            _delete_all_surcharge_chips(db, reservation_id, date)
            return

        # 2. Room 조회 및 도미토리 스킵
        room = db.query(Room).filter(Room.id == assignment.room_id).first()
        if room is None:
            return

        if room.is_dormitory:
            return

        # 3. 예약 조회 및 게스트 수 계산
        reservation = db.query(Reservation).filter(
            Reservation.id == reservation_id
        ).first()
        if reservation is None:
            return

        guest_count = (
            reservation.party_size
            or (reservation.male_count or 0) + (reservation.female_count or 0)
            or 1
        )

        # 4. 초과 인원 계산
        excess = guest_count - room.base_capacity

        # 5. 각 레벨별로 칩 생성/삭제
        for level in SURCHARGE_LEVELS:
            custom_type = _custom_type_for_level(level)

            # 해당 레벨의 스케줄 조회 (스케줄에 연결된 템플릿 사용)
            schedule = _find_schedule(db, custom_type)

            # 기존 칩 조회 (schedule_id 기반)
            existing = None
            if schedule:
                existing = db.query(ReservationSmsAssignment).filter(
                    ReservationSmsAssignment.reservation_id == reservation_id,
                    ReservationSmsAssignment.date == date,
                    ReservationSmsAssignment.schedule_id == schedule.id,
                ).first()

            if excess == level:
                # 이 레벨에 해당 → 칩 있으면 유지, 없으면 생성
                if existing:
                    continue

                # 스케줄이 없으면 칩 생성 스킵
                if not schedule:
                    continue

                # 스케줄에 연결된 템플릿의 template_key 사용
                if not schedule.template:
                    logger.warning(
                        "surcharge: 스케줄에 템플릿 미연결 (schedule_id=%s, reservation_id=%s)",
                        schedule.id, reservation_id,
                    )
                    continue

                target_key = schedule.template.template_key
                tenant_id = current_tenant_id.get()
                new_chip = ReservationSmsAssignment(
                    reservation_id=reservation_id,
                    template_key=target_key,
                    date=date,
                    assigned_by='auto',
                    schedule_id=schedule.id,
                    sent_at=None,
                    tenant_id=tenant_id,
                )
                db.add(new_chip)
                logger.info(
                    "surcharge: 칩 생성 (%s, schedule_id=%s, reservation_id=%s, date=%s)",
                    target_key, schedule.id, reservation_id, date,
                )
                diag(
                    "surcharge.chip_created",
                    level="verbose",
                    res_id=reservation_id,
                    date=date,
                    level_val=level,
                    template_key=target_key,
                )
            else:
                # 이 레벨에 해당 안 함 → 미발송 칩 삭제
                if existing and existing.sent_at is None:
                    db.delete(existing)
                    logger.debug(
                        "surcharge: 칩 삭제 (%s, reservation_id=%s, date=%s)",
                        custom_type, reservation_id, date,
                    )
                    diag(
                        "surcharge.chip_deleted",
                        level="verbose",
                        res_id=reservation_id,
                        date=date,
                        level_val=level,
                    )

        db.flush()

    except Exception:
        logger.exception(
            "surcharge: reconcile_surcharge 실패 (reservation_id=%s, date=%s)",
            reservation_id, date,
        )


def _delete_all_surcharge_chips(db: Session, reservation_id: int, date: str) -> None:
    """해당 예약-날짜의 미발송 surcharge 칩을 모두 삭제합니다."""
    # 모든 surcharge 스케줄 ID 조회
    surcharge_schedule_ids = [
        s.id for s in db.query(TemplateSchedule.id).filter(
            TemplateSchedule.schedule_category == 'custom_schedule',
            TemplateSchedule.custom_type.like('surcharge_%'),
        ).all()
    ]
    if not surcharge_schedule_ids:
        return

    deleted = db.query(ReservationSmsAssignment).filter(
        ReservationSmsAssignment.reservation_id == reservation_id,
        ReservationSmsAssignment.date == date,
        ReservationSmsAssignment.schedule_id.in_(surcharge_schedule_ids),
        ReservationSmsAssignment.sent_at.is_(None),
    ).delete(synchronize_session='fetch')
    if deleted:
        db.flush()
        logger.debug(
            "surcharge: 전체 삭제 %d건 (reservation_id=%s, date=%s)",
            deleted, reservation_id, date,
        )
        diag(
            "surcharge.all_deleted",
            level="verbose",
            res_id=reservation_id,
            date=date,
            count=deleted,
        )


def reconcile_surcharge_batch(
    db: Session,
    reservation_ids: List[int],
    date: str,
) -> None:
    """
    여러 예약에 대해 일괄 추가요금 칩 재조정을 수행합니다.
    개별 실패가 전체를 차단하지 않습니다.
    """
    diag("surcharge.batch.enter", level="verbose", count=len(reservation_ids))
    for reservation_id in reservation_ids:
        try:
            reconcile_surcharge(db, reservation_id, date)
        except Exception:
            logger.exception(
                "surcharge: batch 처리 중 예외 (reservation_id=%s, date=%s)",
                reservation_id, date,
            )
    diag("surcharge.batch.exit", level="verbose", count=len(reservation_ids))
