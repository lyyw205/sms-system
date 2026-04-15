"""
SMS 발송 추적 공통 헬퍼
ReservationSmsAssignment upsert를 한 곳에서 관리
"""
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.db.models import ReservationSmsAssignment
import logging

logger = logging.getLogger(__name__)


def record_sms_sent(
    db: Session,
    reservation_id: int,
    template_key: str,
    sms_type_label: str,
    assigned_by: str = "auto",
    date: str = "",
) -> None:
    """
    SMS 발송 성공 기록을 ReservationSmsAssignment에 upsert.
    """
    existing = (
        db.query(ReservationSmsAssignment)
        .filter(
            ReservationSmsAssignment.reservation_id == reservation_id,
            ReservationSmsAssignment.template_key == template_key,
            ReservationSmsAssignment.date == date,
        )
        .first()
    )

    if existing:
        existing.sent_at = datetime.now(timezone.utc)
        existing.send_status = 'sent'
        existing.send_error = None
    else:
        db.add(ReservationSmsAssignment(
            reservation_id=reservation_id,
            template_key=template_key,
            assigned_by=assigned_by,
            sent_at=datetime.now(timezone.utc),
            send_status='sent',
            date=date,
        ))


def record_sms_failed(
    db: Session,
    reservation_id: int,
    template_key: str,
    error: str,
    date: str = "",
) -> None:
    """
    SMS 발송 실패 기록. 칩에 send_status='failed'와 에러 메시지를 기록.
    다음 스케줄 실행 시 재시도하지 않음.
    """
    existing = (
        db.query(ReservationSmsAssignment)
        .filter(
            ReservationSmsAssignment.reservation_id == reservation_id,
            ReservationSmsAssignment.template_key == template_key,
            ReservationSmsAssignment.date == date,
        )
        .first()
    )

    if existing:
        existing.send_status = 'failed'
        existing.send_error = (error or 'unknown')[:500]
    else:
        db.add(ReservationSmsAssignment(
            reservation_id=reservation_id,
            template_key=template_key,
            assigned_by='auto',
            send_status='failed',
            send_error=(error or 'unknown')[:500],
            date=date,
        ))
