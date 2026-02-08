"""
Webhook endpoints for SMS and external integrations
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.database import get_db
from app.db.models import Message, MessageDirection, MessageStatus
from app.factory import get_sms_provider
from app.router.message_router import message_router
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
    Saves inbound message, runs auto-response pipeline, and auto-sends if confident.
    """
    sms_provider = get_sms_provider()

    # Simulate SMS reception
    result = await sms_provider.simulate_receive(
        from_=request.from_, to=request.to, message=request.message
    )

    # Save inbound message to DB
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

    # Auto-response pipeline
    auto_result = await message_router.generate_auto_response(request.message)

    # Store auto-response metadata on inbound message
    msg.auto_response = auto_result["response"]
    msg.auto_response_confidence = auto_result["confidence"]
    msg.needs_review = auto_result["needs_review"]
    msg.response_source = auto_result["source"]
    db.commit()

    response = {
        "status": "success",
        "message_id": msg.id,
        "result": result,
        "auto_response": {
            "response": auto_result["response"],
            "confidence": auto_result["confidence"],
            "needs_review": auto_result["needs_review"],
            "source": auto_result["source"],
            "sent": False,
        },
    }

    # Auto-send if no review needed
    if not auto_result["needs_review"]:
        await sms_provider.send_sms(to=request.from_, message=auto_result["response"])

        outbound_msg = Message(
            message_id=f"auto_{msg.id}_{int(datetime.utcnow().timestamp())}",
            direction=MessageDirection.OUTBOUND,
            from_=request.to,
            to=request.from_,
            message=auto_result["response"],
            status=MessageStatus.SENT,
            response_source=auto_result["source"],
            auto_response_confidence=auto_result["confidence"],
        )
        db.add(outbound_msg)
        db.commit()
        db.refresh(outbound_msg)

        response["auto_response"]["sent"] = True
        response["outbound_message"] = {
            "id": outbound_msg.id,
            "message": outbound_msg.message,
        }
        logger.info(f"Auto-response sent: {outbound_msg.id} (source={auto_result['source']})")
    else:
        logger.info(f"Auto-response needs review (confidence={auto_result['confidence']:.2f})")

    return response
