"""
SSE endpoint for real-time event streaming to frontend clients.
"""
import asyncio
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.event_bus import subscribe, unsubscribe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/stream")
async def event_stream():
    """
    Server-Sent Events stream. Clients subscribe here to receive real-time
    notifications (e.g. schedule_complete) without polling.
    """
    q = subscribe()

    async def generator():
        try:
            # Send an initial keep-alive comment so the browser confirms the connection
            yield ": connected\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive ping every 30 s
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
