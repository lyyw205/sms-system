"""
Webhook endpoints for SMS and external integrations
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.database import get_db
from app.db.models import Message, MessageDirection, MessageStatus
from app.factory import get_sms_provider
from datetime import datetime
import logging

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


class SMSReceiveRequest(BaseModel):
    from_: str
    to: str
    message: str


@router.post("/sms/receive")
async def receive_sms(request: SMSReceiveRequest, db: Session = Depends(get_db)):
    """
    Webhook for receiving SMS (simulated in demo mode).
    In production, this will be called by real SMS provider webhook.
    """
    sms_provider = get_sms_provider()

    # Simulate SMS reception
    result = await sms_provider.simulate_receive(
        from_=request.from_, to=request.to, message=request.message
    )

    # Save to DB
    msg = Message(
        message_id=result["message_id"],
        direction=MessageDirection.INBOUND,
        from_=request.from_,
        to=request.to,
        message=request.message,
        status=MessageStatus.RECEIVED,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    logger.info(f"SMS received and saved to DB: {msg.id}")

    return {"status": "success", "message_id": msg.id, "result": result}
