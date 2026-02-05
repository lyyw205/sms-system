"""
Real Reservation Provider stub - to be implemented after contract
"""
from typing import List, Dict, Any, Optional


class RealReservationProvider:
    """Real reservation provider using Naver Booking API or web scraping"""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    async def sync_reservations(self) -> List[Dict[str, Any]]:
        """
        Fetch reservations from Naver Booking

        Implementation TODO:
        1. Check if Naver provides official API
        2. If not, use Playwright/Selenium for web scraping
        3. Login to Naver Booking
        4. Parse reservation list
        5. Return standardized format

        Implementation time: ~2 hours
        """
        raise NotImplementedError("Real reservation provider not implemented yet")

    async def get_reservation_details(self, reservation_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed reservation info from Naver"""
        raise NotImplementedError("Real reservation provider not implemented yet")
