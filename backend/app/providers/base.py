"""
Abstract provider interfaces using Protocol (PEP 544).
This allows hot-swapping between Mock and Real implementations.
"""
from typing import Protocol, Any, Dict, List, Optional
from datetime import datetime


class SMSProvider(Protocol):
    """SMS sending/receiving abstraction"""

    async def send_sms(self, to: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send SMS message"""
        ...

    async def simulate_receive(self, from_: str, to: str, message: str) -> Dict[str, Any]:
        """Simulate receiving SMS (for demo mode)"""
        ...


class ReservationProvider(Protocol):
    """Reservation sync abstraction (Naver Booking)"""

    async def sync_reservations(self) -> List[Dict[str, Any]]:
        """Fetch reservations from external source"""
        ...

    async def get_reservation_details(self, reservation_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed reservation info"""
        ...


class LLMProvider(Protocol):
    """LLM (Claude) abstraction for auto-response generation"""

    async def generate_response(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate response to customer message.
        Returns: {
            "response": str,
            "confidence": float (0-1),
            "needs_review": bool
        }
        """
        ...


class StorageProvider(Protocol):
    """External storage abstraction (Google Sheets)"""

    async def sync_to_storage(self, data: List[Dict[str, Any]], sheet_name: str) -> bool:
        """Export data to external storage"""
        ...

    async def sync_from_storage(self, sheet_name: str) -> List[Dict[str, Any]]:
        """Import data from external storage"""
        ...
