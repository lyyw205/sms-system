"""
Message API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.db.database import get_db
from app.db.models import Message, MessageDirection, MessageStatus
from app.factory import get_sms_provider
from datetime import datetime

router = APIRouter(prefix="/api/messages", tags=["messages"])


class SendSMSRequest(BaseModel):
    to: str
    message: str


class SimulateReceiveRequest(BaseModel):
    from_: str
    to: str
    message: str


class MessageResponse(BaseModel):
    id: int
    message_id: str
    direction: str
    from_: str
    to: str
    message: str
    status: str
    created_at: datetime
    auto_response: Optional[str] = None
    auto_response_confidence: Optional[float] = None
    needs_review: bool = False
    response_source: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[MessageResponse])
async def get_messages(
    skip: int = 0, limit: int = 50, direction: Optional[str] = None, db: Session = Depends(get_db)
):
    """Get message history with pagination"""
    query = db.query(Message)

    if direction:
        query = query.filter(Message.direction == direction)

    messages = query.order_by(Message.created_at.desc()).offset(skip).limit(limit).all()

    return [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            direction=msg.direction.value,
            from_=msg.from_,
            to=msg.to,
            message=msg.message,
            status=msg.status.value,
            created_at=msg.created_at,
            auto_response=msg.auto_response,
            auto_response_confidence=msg.auto_response_confidence,
            needs_review=msg.needs_review,
            response_source=msg.response_source,
        )
        for msg in messages
    ]


@router.post("/send")
async def send_sms(request: SendSMSRequest, db: Session = Depends(get_db)):
    """Send SMS manually"""
    sms_provider = get_sms_provider()
    result = await sms_provider.send_sms(to=request.to, message=request.message)

    # Save to DB
    msg = Message(
        message_id=result["message_id"],
        direction=MessageDirection.OUTBOUND,
        from_="010-9999-0000",
        to=request.to,
        message=request.message,
        status=MessageStatus.SENT,
        response_source="manual",
    )
    db.add(msg)
    db.commit()

    return {"status": "success", "result": result}


@router.get("/review-queue")
async def get_review_queue(db: Session = Depends(get_db)):
    """Get messages that need human review"""
    messages = (
        db.query(Message)
        .filter(Message.needs_review == True, Message.direction == MessageDirection.INBOUND)
        .order_by(Message.created_at.desc())
        .all()
    )

    return [
        MessageResponse(
            id=msg.id,
            message_id=msg.message_id,
            direction=msg.direction.value,
            from_=msg.from_,
            to=msg.to,
            message=msg.message,
            status=msg.status.value,
            created_at=msg.created_at,
            auto_response=msg.auto_response,
            auto_response_confidence=msg.auto_response_confidence,
            needs_review=msg.needs_review,
            response_source=msg.response_source,
        )
        for msg in messages
    ]
