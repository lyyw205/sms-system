"""Batch room lookup utilities to avoid N+1 queries."""
from typing import Optional
from sqlalchemy.orm import Session

from app.db.models import Room, RoomAssignment


def batch_room_lookup(
    db: Session,
    reservation_ids: list[int],
    target_date: Optional[str] = None,
) -> dict[int, dict]:
    """Batch lookup room info for reservations.

    Args:
        reservation_ids: 조회할 예약 ID 목록.
        target_date: YYYY-MM-DD. 지정하면 해당 날짜 배정만 조회. None 이면
            예약당 **가장 이른 체크인 날짜** 의 배정을 반환 (order_by date 로 결정적 보장).

    Returns:
        {reservation_id: {"room_id", "room_number", "room_password", "assigned_by", "bed_order"}}

    Note:
        target_date=None 정책은 "첫 밤 방 정보" 가 기본값 (예: 예약 상세 페이지에서 첫날
        방 표시). 호출자가 특정 날짜 정보가 필요하면 target_date 를 명시해야 함.
    """
    if not reservation_ids:
        return {}

    # order_by(date) 로 가장 이른 배정이 먼저 오게 고정 — "첫 밤 기준" 결정적 선택 보장
    query = db.query(RoomAssignment).filter(
        RoomAssignment.reservation_id.in_(reservation_ids),
    ).order_by(RoomAssignment.date.asc())
    if target_date:
        query = query.filter(RoomAssignment.date == target_date)

    assignments = query.all()

    # Build reservation_id -> assignment mapping (first = earliest date per reservation)
    ra_map: dict[int, RoomAssignment] = {}
    for ra in assignments:
        if ra.reservation_id not in ra_map:
            ra_map[ra.reservation_id] = ra

    # Batch fetch rooms
    room_ids = {ra.room_id for ra in ra_map.values() if ra.room_id}
    if not room_ids:
        return {}

    rooms = db.query(Room).filter(Room.id.in_(room_ids)).all()
    room_map = {rm.id: rm for rm in rooms}

    result = {}
    for res_id, ra in ra_map.items():
        rm = room_map.get(ra.room_id)
        result[res_id] = {
            "room_id": ra.room_id,
            "room_number": rm.room_number if rm else None,
            "room_password": ra.room_password,
            "assigned_by": ra.assigned_by,
            "bed_order": ra.bed_order or 0,
        }
    return result


def batch_room_number_map(
    db: Session,
    reservation_ids: list[int],
    target_date: str,
) -> dict[int, str]:
    """Simple batch lookup: reservation_id -> room_number string.

    Convenience wrapper for cases that only need room_number.
    """
    lookup = batch_room_lookup(db, reservation_ids, target_date)
    return {res_id: info["room_number"] or "" for res_id, info in lookup.items()}
