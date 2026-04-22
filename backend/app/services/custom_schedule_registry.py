"""
custom_schedule_registry.py — 커스텀 스케줄 로직 레지스트리

새 커스텀 로직 추가 시 이 파일의 CUSTOM_SCHEDULE_TYPES에 등록하면
API를 통해 프론트엔드 드롭다운에 자동으로 반영됩니다.

Pre-send refresh:
  스케줄 실행(13:25 등) 직전에 해당 custom_type 의 칩 상태를 최신으로
  맞추기 위해 호출되는 handler 를 등록합니다. 핸들러는 DB 세션과
  target_date 를 받아 reconcile 함수를 호출하고, 발송 로직은 그 결과를
  Eligibility 필터의 기준으로 사용합니다.
"""
from typing import Callable

from sqlalchemy.orm import Session


# 커스텀 스케줄 타입 레지스트리
# key: custom_type 값 (DB에 저장됨)
# label: UI에 표시되는 한글 라벨
CUSTOM_SCHEDULE_TYPES = {
    "surcharge_standard": "인원 초과 (일반 객실)",
    "surcharge_double": "인원 초과 (더블 객실, 업그레이드비 포함)",
}


def get_custom_types() -> list[dict]:
    """프론트엔드 드롭다운용 커스텀 타입 목록 반환."""
    return [
        {"value": key, "label": label}
        for key, label in CUSTOM_SCHEDULE_TYPES.items()
    ]


def _refresh_surcharge(db: Session, target_date: str) -> None:
    """surcharge_* 타입 발송 직전 칩 상태 최신화.

    target_date 에 배정된 모든 예약에 대해 reconcile_surcharge 를 다시 호출해
    트리거 누락/상황 변경으로 stale 해진 칩을 정리한다.
    """
    from app.db.models import RoomAssignment
    from app.services.surcharge import reconcile_surcharge_batch

    rows = (
        db.query(RoomAssignment.reservation_id)
        .filter(RoomAssignment.date == target_date)
        .all()
    )
    reservation_ids = [row[0] for row in rows]
    if not reservation_ids:
        return
    reconcile_surcharge_batch(db, reservation_ids, target_date)


# custom_type → (db, target_date) -> None
# 같은 reconcile 로직을 공유하는 타입은 같은 handler 를 가리키면 됨.
PRE_SEND_REFRESH_HANDLERS: dict[str, Callable[[Session, str], None]] = {
    "surcharge_standard": _refresh_surcharge,
    "surcharge_double": _refresh_surcharge,
}


def get_pre_send_refresh_handler(custom_type: str | None) -> Callable[[Session, str], None] | None:
    """custom_type 에 등록된 refresh handler 를 반환. 없으면 None."""
    if not custom_type:
        return None
    return PRE_SEND_REFRESH_HANDLERS.get(custom_type)
