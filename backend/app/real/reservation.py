"""
Real Reservation Provider - Naver Booking API integration
Ported from stable-clasp-main/00_main.js
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
import logging

logger = logging.getLogger(__name__)


class RealReservationProvider:
    """Real reservation provider using Naver Booking API"""

    def __init__(self, email: str, password: str, business_id: str = "819409"):
        self.email = email
        self.password = password
        self.business_id = business_id
        self.cookie = None
        self.base_url = "https://partner.booking.naver.com"

        # Room type mapping (bizItemId -> room info)
        self.room_types = {
            # Will be populated dynamically or configured
        }

    async def _ensure_authenticated(self) -> bool:
        """
        Ensure we have valid authentication cookie.
        For now, expects cookie to be set manually or via environment.
        TODO: Implement automatic login if needed
        """
        if not self.cookie:
            logger.warning("No authentication cookie set. Please set cookie manually.")
            return False
        return True

    async def sync_reservations(self, target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch reservations from Naver Booking API

        Args:
            target_date: Date to fetch reservations for (defaults to today)

        Returns:
            List of reservation dictionaries with standardized format

        Ported from: stable-clasp-main/00_main.js:547-844 (fetchDataAndFillSheetWithDate)
        """
        if target_date is None:
            target_date = datetime.now()

        if not await self._ensure_authenticated():
            logger.error("Authentication required")
            return []

        # Format date for API
        date_str = target_date.strftime("%Y-%m-%d")
        start_datetime = f"{date_str}T01%3A03%3A09.198Z"
        end_datetime = f"{date_str}T01%3A03%3A09.198Z"

        # Build API URL (from line 570 of 00_main.js)
        url = (
            f"{self.base_url}/api/businesses/{self.business_id}/bookings"
            f"?bizItemTypes=STANDARD"
            f"&bookingStatusCodes="
            f"&dateDropdownType=TODAY"
            f"&dateFilter=USEDATE"
            f"&endDateTime={end_datetime}"
            f"&maxDays=31"
            f"&nPayChargedStatusCodes="
            f"&orderBy="
            f"&orderByStartDate=ASC"
            f"&paymentStatusCodes="
            f"&searchValue="
            f"&searchValueCode=USER_NAME"
            f"&startDateTime={start_datetime}"
            f"&page=0"
            f"&size=200"
            f"&noCache=1694307842200"
        )

        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': f'{self.base_url}/bizes/{self.business_id}/booking-list-view',
            'Sec-Ch-Ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            'Cookie': self.cookie
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()

                data = response.json()
                logger.info(f"Fetched {len(data)} reservations from Naver API")

                # Filter for confirmed reservations (RC03) - from line 612
                confirmed = [
                    item for item in data
                    if item.get('bookingStatusCode') == 'RC03'
                    and self._format_date(item.get('endDate')) != date_str
                ]

                # Filter for cancelled reservations (RC04)
                cancelled = [
                    item for item in data
                    if item.get('bookingStatusCode') == 'RC04'
                    and self._format_date(item.get('endDate')) != date_str
                ]

                # Remove duplicates (cancelled that are also in confirmed)
                # From line 630-640
                cancelled_filtered = []
                for cancel_item in cancelled:
                    is_duplicate = False
                    for confirm_item in confirmed:
                        if (cancel_item.get('bizItemId') == confirm_item.get('bizItemId')
                            and cancel_item.get('name') == confirm_item.get('name')
                            and cancel_item.get('phone') == confirm_item.get('phone')):
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        cancelled_filtered.append(cancel_item)

                logger.info(f"Confirmed: {len(confirmed)}, Cancelled: {len(cancelled_filtered)}")

                # Detect multi-bookings (same name+phone, multiple bookings)
                # From line 644-660
                multi_booking_ids = self._detect_multi_bookings(confirmed)

                # Convert to standardized format
                reservations = []
                for item in confirmed:
                    reservation = self._parse_reservation(item, multi_booking_ids)
                    reservations.append(reservation)

                return reservations

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching reservations: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching reservations: {e}")
            return []

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from Naver API

        Returns:
            Dictionary with age_group, gender, visit_count

        Ported from: stable-clasp-main/00_main.js:488-545 (fetchUserInfo)
        """
        if not await self._ensure_authenticated():
            return None

        url = f"{self.base_url}/v3.0/businesses/{self.business_id}/users/{user_id}"

        headers = {
            'Accept': '*/*',
            'Cookie': self.cookie
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()

                data = response.json()

                # Parse age and gender from response (from line 520-541)
                age_group = data.get('ageRange', '')
                gender = '남' if data.get('sex') == 'MALE' else '여' if data.get('sex') == 'FEMALE' else ''
                visit_count = data.get('completedCount', 0) + 1

                return {
                    'age_group': age_group,
                    'gender': gender,
                    'visit_count': visit_count
                }

        except Exception as e:
            logger.error(f"Error fetching user info for {user_id}: {e}")
            return None

    async def get_reservation_details(self, reservation_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed reservation info"""
        # For now, details are included in sync_reservations response
        # Can be enhanced if needed
        return None

    def _format_date(self, date_str: Optional[str]) -> str:
        """Format date string to YYYY-MM-DD"""
        if not date_str:
            return ""
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d")
        except:
            return ""

    def _detect_multi_bookings(self, reservations: List[Dict]) -> set:
        """
        Detect bookings where same person (name+phone) has multiple reservations
        Returns set of booking IDs that are multi-bookings

        From line 644-660
        """
        booking_map = {}
        for item in reservations:
            key = f"{item.get('name')}_{item.get('phone')}"
            if key not in booking_map:
                booking_map[key] = []
            booking_map[key].append(item.get('bookingId'))

        multi_booking_ids = set()
        for key, booking_ids in booking_map.items():
            if len(booking_ids) > 1:
                multi_booking_ids.update(booking_ids)

        return multi_booking_ids

    def _parse_reservation(self, item: Dict[str, Any], multi_booking_ids: set) -> Dict[str, Any]:
        """
        Parse Naver API reservation item to standardized format
        """
        return {
            'external_id': str(item.get('bookingId', '')),
            'naver_booking_id': str(item.get('bookingId', '')),
            'naver_biz_item_id': str(item.get('bizItemId', '')),
            'customer_name': item.get('name', ''),
            'phone': item.get('phone', ''),
            'visitor_name': item.get('visitorName'),
            'visitor_phone': item.get('visitorPhone'),
            'date': self._format_date(item.get('startDate')),
            'time': item.get('startTime', ''),
            'status': 'confirmed',
            'source': 'naver',
            'is_multi_booking': str(item.get('bookingId')) in multi_booking_ids,
            'raw_data': item  # Store raw data for reference
        }

    def get_room_name(self, biz_item_id: str) -> Optional[str]:
        """
        Map bizItemId to room name

        From stable-clasp-main/03_trigger.js:225-272 (getRoomName)
        TODO: Load from configuration or database
        """
        return self.room_types.get(biz_item_id)
