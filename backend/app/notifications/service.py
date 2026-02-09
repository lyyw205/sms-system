"""
Notification Service - Automated SMS sending for room and party guides
Ported from stable-clasp-main/00_main.js
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from ..db.models import Reservation, CampaignLog
from ..providers.base import SMSProvider, StorageProvider
from ..templates.renderer import TemplateRenderer

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for automated notification sending

    Ported from: stable-clasp-main/00_main.js (roomGuideInRange, partyGuideInRange)
    """

    def __init__(
        self,
        db: Session,
        sms_provider: SMSProvider,
        storage_provider: Optional[StorageProvider] = None
    ):
        self.db = db
        self.sms_provider = sms_provider
        self.storage_provider = storage_provider
        self.renderer = TemplateRenderer(db)

    async def send_room_guide(
        self,
        date: Optional[datetime] = None,
        start_row: int = 3,
        end_row: int = 68
    ) -> CampaignLog:
        """
        Send room guide messages to confirmed guests

        Args:
            date: Target date (defaults to today)
            start_row: Starting row in sheet
            end_row: Ending row in sheet

        Returns:
            CampaignLog record

        Ported from: stable-clasp-main/00_main.js:58-249 (roomGuideInRange)
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y-%m-%d")

        # Create campaign log
        campaign = CampaignLog(
            campaign_type='room_guide',
            sent_at=datetime.utcnow()
        )

        try:
            # Get reservations for the date that haven't received room SMS
            reservations = self.db.query(Reservation).filter(
                Reservation.date == date_str,
                Reservation.room_sms_sent == False,
                Reservation.room_number.isnot(None),
                Reservation.phone.isnot(None)
            ).all()

            campaign.target_count = len(reservations)

            if not reservations:
                logger.info(f"No room guide targets for {date_str}")
                campaign.completed_at = datetime.utcnow()
                self.db.add(campaign)
                self.db.commit()
                return campaign

            # Prepare messages
            messages = []
            phone_numbers = []

            for reservation in reservations:
                # Generate room password if not set
                if not reservation.room_password:
                    reservation.room_password = TemplateRenderer.generate_room_password(
                        reservation.room_number
                    )

                # Render message
                message = self.renderer.render_room_guide(reservation)

                messages.append({
                    'to': reservation.phone,
                    'message': message
                })
                phone_numbers.append(reservation.phone)

            # Send bulk SMS
            logger.info(f"Sending {len(messages)} room guide messages")

            result = await self.sms_provider.send_bulk(messages)

            if result.get('success'):
                campaign.sent_count = len(messages)

                # Mark as sent
                for reservation in reservations:
                    reservation.room_sms_sent = True
                    reservation.room_sms_sent_at = datetime.utcnow()

                    # Update sent_sms_types
                    current_types = reservation.sent_sms_types or ""
                    types_list = [t.strip() for t in current_types.split(',') if t.strip()]
                    if "객실안내" not in types_list:
                        types_list.append("객실안내")
                        reservation.sent_sms_types = ','.join(types_list)

                # Mark in Google Sheets if provider available
                if self.storage_provider:
                    await self.storage_provider.mark_sent_phone_numbers(
                        phone_numbers,
                        date,
                        '객실문자O'
                    )

                logger.info(f"Room guide campaign successful: {campaign.sent_count} sent")

            else:
                campaign.failed_count = len(messages)
                campaign.error_message = result.get('error', 'Unknown error')
                logger.error(f"Room guide campaign failed: {campaign.error_message}")

            campaign.completed_at = datetime.utcnow()
            self.db.add(campaign)
            self.db.commit()

            return campaign

        except Exception as e:
            logger.error(f"Error in room guide campaign: {e}")
            campaign.error_message = str(e)
            campaign.completed_at = datetime.utcnow()
            self.db.add(campaign)
            self.db.commit()
            raise

    async def send_party_guide(
        self,
        date: Optional[datetime] = None,
        start_row: int = 3,
        end_row: int = 68
    ) -> CampaignLog:
        """
        Send party guide messages to unassigned guests

        Args:
            date: Target date (defaults to today)
            start_row: Starting row in sheet
            end_row: Ending row in sheet

        Returns:
            CampaignLog record

        Ported from: stable-clasp-main/00_main.js:251-480 (partyGuideInRange)
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y-%m-%d")

        # Create campaign log
        campaign = CampaignLog(
            campaign_type='party_guide',
            sent_at=datetime.utcnow()
        )

        try:
            # Get reservations that haven't received party SMS
            reservations = self.db.query(Reservation).filter(
                Reservation.date == date_str,
                Reservation.party_sms_sent == False,
                Reservation.phone.isnot(None)
            ).all()

            campaign.target_count = len(reservations)

            if not reservations:
                logger.info(f"No party guide targets for {date_str}")
                campaign.completed_at = datetime.utcnow()
                self.db.add(campaign)
                self.db.commit()
                return campaign

            # Count total participants (from line 281-292)
            total_participants = sum(
                r.party_participants for r in reservations
                if r.party_participants
            )

            # Round up to nearest 10 and add 10 (from line 312)
            import math
            total_participants = math.ceil(total_participants / 10) * 10 + 10

            logger.info(f"Total party participants: {total_participants}")

            # Check if weekend (Friday or Saturday) - from line 332-335
            is_weekend = date.weekday() in [4, 5]

            # Build party price message (from line 315-349)
            party_price = self._get_party_price_message(is_weekend)

            # Build full message
            message = f"""
금일 파티 참여 시 아래 계좌로 파티비 입금 후 저녁 8시 스테이블 B동 1층 "포차"로 내려와주세요 !
우리은행 1002-053-970545 (배경태)

{party_price}

- 금일 파티 인원은 {total_participants}명+ 예상됨(여자2~4명)
- 조별활동이 있으니 편한 옷차림으로 내려와주세요.
(인스타그램 @stay.ble 참고)
- 쓰레기는 2개 분리수거함에 분류하여 버려주세요.
- 제주 날씨는 변덕스럽습니다. 실내외 모두 진행되는 행사이니 긴 바지 및 얇은 점퍼 지참 권장합니다.
- 행사 종료 전 퇴장하실 분은 인스타그램 DM으로 알려주세요.
- 저녁 8시 이후에 도착하실 분은 먼저 시작하고 있으니 도착 시 자리로 와주세요!
- 카톡플친 하시면 이벤트 및 프로모션 받으실 수 있어요 :) http://pf.kakao.com/_Txlxoxgxj/chat
""".strip()

            # Send to all targets
            messages = []
            phone_numbers = []

            for reservation in reservations:
                messages.append({
                    'to': reservation.phone,
                    'message': message
                })
                phone_numbers.append(reservation.phone)

            # Send bulk SMS
            logger.info(f"Sending {len(messages)} party guide messages")

            result = await self.sms_provider.send_bulk(messages)

            if result.get('success'):
                campaign.sent_count = len(messages)

                # Mark as sent
                for reservation in reservations:
                    reservation.party_sms_sent = True
                    reservation.party_sms_sent_at = datetime.utcnow()

                    # Update sent_sms_types
                    current_types = reservation.sent_sms_types or ""
                    types_list = [t.strip() for t in current_types.split(',') if t.strip()]
                    if "파티안내" not in types_list:
                        types_list.append("파티안내")
                        reservation.sent_sms_types = ','.join(types_list)

                # Mark in Google Sheets if provider available
                if self.storage_provider:
                    await self.storage_provider.mark_sent_phone_numbers(
                        phone_numbers,
                        date,
                        '파티문자O'
                    )

                logger.info(f"Party guide campaign successful: {campaign.sent_count} sent")

            else:
                campaign.failed_count = len(messages)
                campaign.error_message = result.get('error', 'Unknown error')
                logger.error(f"Party guide campaign failed: {campaign.error_message}")

            campaign.completed_at = datetime.utcnow()
            self.db.add(campaign)
            self.db.commit()

            return campaign

        except Exception as e:
            logger.error(f"Error in party guide campaign: {e}")
            campaign.error_message = str(e)
            campaign.completed_at = datetime.utcnow()
            self.db.add(campaign)
            self.db.commit()
            raise

    def _get_party_price_message(self, is_weekend: bool) -> str:
        """
        Get party pricing message based on day of week

        Args:
            is_weekend: Whether it's Friday or Saturday

        Returns:
            Formatted price message

        Ported from: stable-clasp-main/00_main.js:315-349
        """
        if is_weekend:
            # Weekend pricing (Friday/Saturday) - from line 338-349
            return """
[1차 파티]
- 오후8시~10시30분
- 흑돼지바베큐 무제한(90분), 설탕토마토, 고구마샐러드, 물만두, 과일안주, 팝콘, 토닉워터 등
- 주류 1병(1인당)
- 남자 3만 원, 여자 2만 원

[2차 파티]
- 오후10시30분~12시30분
- 치킨, 시원한 콩나물국, 과자, 샐러드
- 주류 1병(2인당)
- 남자 2.5만 원, 여자 2만 원

- 1차+2차 신청 시 남자 5.5만원 / 여자 4만원
(금일 인원이 많아 1차 이후 현장 2차 신청이 안될 수 있으니 꼭 동시 신청해주세요!)
            """.strip()
        else:
            # Weekday pricing - from line 315-330
            return """
[1차 파티]
- 오후8시~10시30분
- 흑돼지바베큐 무제한(90분), 설탕토마토, 고구마샐러드, 물만두, 과일안주, 팝콘, 토닉워터 등
- 주류 1병(1인당)
- 남자 3만 원, 여자 2만 원

[2차 파티]
- 오후10시30분~12시30분
- 치킨, 시원한 콩나물국, 과자, 샐러드
- 주류 1병(2인당)
- 남자 2.5만 원, 여자 2만 원

- 1차+2차 신청 시 남자 5.5만원 / 여자 4만원
(금일 인원이 많아 1차 이후 현장 2차 신청이 안될 수 있으니 꼭 동시 신청해주세요!)
            """.strip()
