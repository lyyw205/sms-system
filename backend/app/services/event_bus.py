"""
Simple in-process event bus using asyncio.Queue for SSE clients.
"""
import asyncio
import json
import logging
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)

_queues: Dict[int, Set[asyncio.Queue]] = {}


def subscribe(tenant_id: int) -> asyncio.Queue:
    """Register a new SSE client for a tenant and return its queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    if tenant_id not in _queues:
        _queues[tenant_id] = set()
    _queues[tenant_id].add(q)
    total = sum(len(s) for s in _queues.values())
    logger.debug(f"SSE client subscribed for tenant {tenant_id} (total: {total})")
    return q


def unsubscribe(q: asyncio.Queue, tenant_id: int) -> None:
    """Remove a client queue when it disconnects."""
    tenant_set = _queues.get(tenant_id)
    if tenant_set is not None:
        tenant_set.discard(q)
        if not tenant_set:
            del _queues[tenant_id]
    total = sum(len(s) for s in _queues.values())
    logger.debug(f"SSE client unsubscribed for tenant {tenant_id} (total: {total})")


def publish(event_type: str, data: dict, tenant_id: Optional[int] = None) -> None:
    """
    Broadcast an event to SSE clients.
    If tenant_id is provided, only broadcast to that tenant's queues.
    If tenant_id is None, broadcast to all queues (backward compatibility).
    Drops the event for any client whose queue is full.
    """
    if not _queues:
        return
    payload = json.dumps({"event": event_type, "data": data})

    if tenant_id is not None:
        target_queues = list(_queues.get(tenant_id, set()))
    else:
        # Broadcast to all tenants
        target_queues = [q for s in _queues.values() for q in list(s)]

    for q in target_queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("SSE queue full for a client, event dropped")
