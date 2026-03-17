"""
Simple in-process event bus using asyncio.Queue for SSE clients.
"""
import asyncio
import json
import logging
from typing import Set

logger = logging.getLogger(__name__)

_queues: Set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    """Register a new SSE client and return its queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _queues.add(q)
    logger.debug(f"SSE client subscribed (total: {len(_queues)})")
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove a client queue when it disconnects."""
    _queues.discard(q)
    logger.debug(f"SSE client unsubscribed (total: {len(_queues)})")


def publish(event_type: str, data: dict) -> None:
    """
    Broadcast an event to all connected SSE clients.
    Drops the event for any client whose queue is full.
    """
    if not _queues:
        return
    payload = json.dumps({"event": event_type, "data": data})
    for q in list(_queues):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("SSE queue full for a client, event dropped")
