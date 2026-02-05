"""
Mock Reservation Provider for demo mode.
Reads reservations from JSON file instead of actual Naver API.
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MockReservationProvider:
    """Mock reservation provider - reads from JSON file"""

    def __init__(self):
        self.data_file = Path("app/mock/data/naver_reservations.json")

    async def sync_reservations(self) -> List[Dict[str, Any]]:
        """Fetch reservations from JSON file (simulating Naver API)"""
        logger.info(
            f"📅 [MOCK NAVER SYNC]\n"
            f"   Reading from: {self.data_file}\n"
            f"   ⚠️  In production mode, this will call Naver Booking API or use web scraping"
        )

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                reservations = json.load(f)
                logger.info(f"   Found {len(reservations)} reservations in mock data")
                return reservations
        except FileNotFoundError:
            logger.warning(f"   Mock data file not found: {self.data_file}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"   Invalid JSON in mock data file: {e}")
            return []

    async def get_reservation_details(self, reservation_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed reservation info"""
        reservations = await self.sync_reservations()
        for res in reservations:
            if res.get("external_id") == reservation_id:
                return res
        return None
