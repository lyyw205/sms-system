"""
Room auto-assignment scheduler job.
Runs daily to assign rooms for today and tomorrow.
Manual assignments (assigned_by='manual') are never overwritten.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.db.models import Reservation, Room, RoomAssignment, ReservationStatus
from app.services import room_assignment

logger = logging.getLogger(__name__)


def auto_assign_rooms(db: Session, target_date: str = None):
    """
    Auto-assign rooms for target_date (defaults to today).
    Only assigns to reservations that have no assignment for that date.
    Never touches manual assignments.

    Called twice per run: once for today, once for tomorrow.
    """
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"Starting room auto-assignment for {target_date}")

    # Get rooms with biz_item_id linked
    rooms_with_biz = (
        db.query(Room)
        .filter(Room.naver_biz_item_id.isnot(None), Room.is_active == True)
        .order_by(Room.sort_order)
        .all()
    )
    if not rooms_with_biz:
        logger.info("No rooms with biz_item_id found, skipping auto-assign")
        return {"target_date": target_date, "assigned": 0, "skipped_manual": 0, "unassigned": 0}

    # Build biz_item_id -> rooms mapping
    biz_to_rooms = {}
    for room in rooms_with_biz:
        biz_to_rooms.setdefault(room.naver_biz_item_id, []).append(room)

    # Get reservations active on target_date that have NO assignment for that date
    unassigned = (
        db.query(Reservation)
        .filter(
            Reservation.naver_biz_item_id.isnot(None),
            Reservation.status == ReservationStatus.CONFIRMED,
            Reservation.date <= target_date,
        )
        .filter(
            ~Reservation.id.in_(
                db.query(RoomAssignment.reservation_id).filter(
                    RoomAssignment.date == target_date
                )
            )
        )
        .all()
    )

    # Filter to only those actually active on target_date
    unassigned = [
        r for r in unassigned
        if r.end_date is None or r.end_date > target_date or r.date == target_date
    ]

    assigned_count = 0
    for res in unassigned:
        candidate_rooms = biz_to_rooms.get(res.naver_biz_item_id, [])
        if not candidate_rooms:
            continue

        for room in candidate_rooms:
            people = (res.party_participants or res.booking_count or 1) if room.is_dormitory else 1

            if room_assignment.check_capacity_all_dates(
                db, room.room_number, target_date, res.end_date,
                people_count=people, exclude_reservation_id=res.id
            ):
                room_assignment.assign_room(
                    db, res.id, room.room_number, target_date, res.end_date,
                    assigned_by="auto"
                )
                assigned_count += 1
                break

    db.commit()

    result = {
        "target_date": target_date,
        "assigned": assigned_count,
        "unassigned": len(unassigned) - assigned_count,
    }
    logger.info(f"Room auto-assignment complete: {result}")
    return result


def daily_assign_rooms(db: Session):
    """
    Daily job: auto-assign rooms for today and tomorrow.
    Only fills in missing assignments, never overwrites manual ones.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    logger.info(f"Running daily room assignment for {today} and {tomorrow}")

    result_today = auto_assign_rooms(db, today)
    result_tomorrow = auto_assign_rooms(db, tomorrow)

    return {
        "today": result_today,
        "tomorrow": result_tomorrow,
    }
