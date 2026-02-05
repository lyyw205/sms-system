"""
Reservations API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.db.database import get_db
from app.db.models import Reservation, ReservationStatus
from app.factory import get_reservation_provider, get_storage_provider
from datetime import datetime
import logging

router = APIRouter(prefix="/api/reservations", tags=["reservations"])
logger = logging.getLogger(__name__)


class ReservationCreate(BaseModel):
    customer_name: str
    phone: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    status: str = "pending"
    notes: Optional[str] = None


class ReservationUpdate(BaseModel):
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ReservationResponse(BaseModel):
    id: int
    external_id: Optional[str] = None
    customer_name: str
    phone: str
    date: str
    time: str
    status: str
    notes: Optional[str] = None
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ReservationResponse])
async def get_reservations(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get reservations with pagination and filtering"""
    query = db.query(Reservation)

    if status:
        query = query.filter(Reservation.status == status)

    reservations = query.order_by(Reservation.created_at.desc()).offset(skip).limit(limit).all()

    return [
        ReservationResponse(
            id=res.id,
            external_id=res.external_id,
            customer_name=res.customer_name,
            phone=res.phone,
            date=res.date,
            time=res.time,
            status=res.status.value,
            notes=res.notes,
            source=res.source,
            created_at=res.created_at,
            updated_at=res.updated_at,
        )
        for res in reservations
    ]


@router.post("", response_model=ReservationResponse)
async def create_reservation(reservation: ReservationCreate, db: Session = Depends(get_db)):
    """Create a new reservation"""
    # Convert status string to enum
    try:
        status_enum = ReservationStatus(reservation.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    db_reservation = Reservation(
        customer_name=reservation.customer_name,
        phone=reservation.phone,
        date=reservation.date,
        time=reservation.time,
        status=status_enum,
        notes=reservation.notes,
        source="manual",
    )
    db.add(db_reservation)
    db.commit()
    db.refresh(db_reservation)

    return ReservationResponse(
        id=db_reservation.id,
        external_id=db_reservation.external_id,
        customer_name=db_reservation.customer_name,
        phone=db_reservation.phone,
        date=db_reservation.date,
        time=db_reservation.time,
        status=db_reservation.status.value,
        notes=db_reservation.notes,
        source=db_reservation.source,
        created_at=db_reservation.created_at,
        updated_at=db_reservation.updated_at,
    )


@router.put("/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_id: int, reservation: ReservationUpdate, db: Session = Depends(get_db)
):
    """Update a reservation"""
    db_reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not db_reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    update_data = reservation.dict(exclude_unset=True)

    # Convert status string to enum if provided
    if "status" in update_data:
        try:
            update_data["status"] = ReservationStatus(update_data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    for field, value in update_data.items():
        setattr(db_reservation, field, value)

    db.commit()
    db.refresh(db_reservation)

    return ReservationResponse(
        id=db_reservation.id,
        external_id=db_reservation.external_id,
        customer_name=db_reservation.customer_name,
        phone=db_reservation.phone,
        date=db_reservation.date,
        time=db_reservation.time,
        status=db_reservation.status.value,
        notes=db_reservation.notes,
        source=db_reservation.source,
        created_at=db_reservation.created_at,
        updated_at=db_reservation.updated_at,
    )


@router.delete("/{reservation_id}")
async def delete_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """Delete a reservation"""
    db_reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not db_reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    db.delete(db_reservation)
    db.commit()
    return {"status": "success", "message": "Reservation deleted"}


@router.post("/sync/naver")
async def sync_from_naver(db: Session = Depends(get_db)):
    """Sync reservations from Naver (mock: reads from JSON file)"""
    logger.info("Starting Naver reservation sync...")

    reservation_provider = get_reservation_provider()
    reservations = await reservation_provider.sync_reservations()

    added_count = 0
    for res_data in reservations:
        # Check if reservation already exists
        existing = (
            db.query(Reservation)
            .filter(Reservation.external_id == res_data.get("external_id"))
            .first()
        )

        if not existing:
            # Convert status string to enum
            try:
                status_enum = ReservationStatus(res_data.get("status", "pending"))
            except ValueError:
                status_enum = ReservationStatus.PENDING

            new_res = Reservation(
                external_id=res_data.get("external_id"),
                customer_name=res_data.get("customer_name"),
                phone=res_data.get("phone"),
                date=res_data.get("date"),
                time=res_data.get("time"),
                status=status_enum,
                notes=res_data.get("notes"),
                source="naver",
            )
            db.add(new_res)
            added_count += 1

    db.commit()
    logger.info(f"Naver sync completed: {added_count} new reservations added")

    return {
        "status": "success",
        "synced": len(reservations),
        "added": added_count,
        "message": f"Synced {len(reservations)} reservations from Naver (mock mode)",
    }


@router.post("/sync/sheets")
async def sync_to_google_sheets(db: Session = Depends(get_db)):
    """Export reservations to Google Sheets (mock: writes to CSV file)"""
    logger.info("Starting Google Sheets sync...")

    # Get all reservations
    reservations = db.query(Reservation).all()

    # Convert to dict format
    data = [
        {
            "id": res.id,
            "external_id": res.external_id or "",
            "customer_name": res.customer_name,
            "phone": res.phone,
            "date": res.date,
            "time": res.time,
            "status": res.status.value,
            "notes": res.notes or "",
            "source": res.source,
            "created_at": res.created_at.isoformat(),
            "updated_at": res.updated_at.isoformat(),
        }
        for res in reservations
    ]

    storage_provider = get_storage_provider()
    success = await storage_provider.sync_to_storage(data, "reservations")

    if success:
        return {
            "status": "success",
            "exported": len(data),
            "message": f"Exported {len(data)} reservations to Google Sheets (mock mode)",
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to sync to Google Sheets")
