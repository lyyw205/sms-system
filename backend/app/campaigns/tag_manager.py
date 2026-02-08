"""
Tag Campaign Manager - Tag-based SMS filtering and sending
Ported from stable-clasp-main/01_sns.js
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from ..db.models import Reservation, CampaignLog
from ..providers.base import SMSProvider

logger = logging.getLogger(__name__)


class TagCampaignManager:
    """
    Manager for tag-based SMS campaigns

    Ported from: stable-clasp-main/01_sns.js
    """

    def __init__(self, db: Session, sms_provider: SMSProvider):
        self.db = db
        self.sms_provider = sms_provider

    def get_targets_by_tag(
        self,
        tag: str,
        exclude_sent: bool = True,
        sms_type: str = 'room',  # 'room' or 'party'
        date: Optional[str] = None,  # YYYY-MM-DD
    ) -> List[Reservation]:
        """
        Get SMS targets filtered by tag

        Args:
            tag: Tag to filter by (supports multi-tags like "1,2,2차만")
            exclude_sent: Whether to exclude already-sent numbers
            sms_type: Type of SMS ('room' or 'party') for marking check
            date: Date filter in YYYY-MM-DD format

        Returns:
            List of Reservation objects matching criteria

        Ported from: stable-clasp-main/01_sns.js:5-33 (collectPhonesByTagAndMark)
        """
        # Multi-tag mapping (from line 8-11)
        multi_tag_map = {
            '1,2,2차만': ['1', '2', '2차만'],
            '2차만': ['2차만']
        }

        # Get target tags
        target_tags = multi_tag_map.get(tag, [tag])

        # Build query
        query = self.db.query(Reservation)

        # Filter by date
        if date:
            query = query.filter(Reservation.date == date)

        # Filter by tags (check if any target tag is in the tags field)
        # Using SQL LIKE for simplicity (tags stored as comma-separated or JSON)
        tag_conditions = []
        for target_tag in target_tags:
            tag_conditions.append(Reservation.tags.contains(target_tag))

        if tag_conditions:
            from sqlalchemy import or_
            query = query.filter(or_(*tag_conditions))

        # Filter by sent status (from line 24-28)
        if exclude_sent:
            if sms_type == 'room':
                query = query.filter(Reservation.room_sms_sent == False)
            elif sms_type == 'party':
                query = query.filter(Reservation.party_sms_sent == False)

        # Filter valid phone numbers (from line 25)
        query = query.filter(Reservation.phone.isnot(None))
        query = query.filter(Reservation.phone != '')

        results = query.all()
        logger.info(f"Found {len(results)} targets for tag '{tag}' date='{date}'")

        return results

    async def send_campaign(
        self,
        tag: str,
        template_key: str,
        variables: Optional[Dict[str, Any]] = None,
        sms_type: str = 'room',
        date: Optional[str] = None,
    ) -> CampaignLog:
        """
        Execute tag-based SMS campaign

        Args:
            tag: Tag to target
            template_key: Message template key
            variables: Template variables (optional)
            sms_type: Type of SMS campaign

        Returns:
            CampaignLog record

        Ported from: stable-clasp-main/01_sns.js:62-124 (sendSmsAndMark)
        """
        # Create campaign log
        campaign = CampaignLog(
            campaign_type='tag_based',
            target_tag=tag,
            sent_at=datetime.utcnow()
        )

        try:
            # Get targets
            targets = self.get_targets_by_tag(tag, exclude_sent=True, sms_type=sms_type, date=date)
            campaign.target_count = len(targets)

            if not targets:
                logger.warning(f"No targets found for tag '{tag}'")
                campaign.completed_at = datetime.utcnow()
                self.db.add(campaign)
                self.db.commit()
                return campaign

            # Prepare messages
            phone_numbers = []
            messages = []

            for reservation in targets:
                # Build message (template rendering would go here)
                # For now, use simple message
                from ..templates.renderer import TemplateRenderer
                renderer = TemplateRenderer(self.db)

                message_vars = variables or {}
                message_vars.update({
                    'name': reservation.customer_name,
                    'roomNumber': reservation.room_number or '',
                    'roomPassword': reservation.room_password or ''
                })

                message = renderer.render(template_key, message_vars)

                messages.append({
                    'to': reservation.phone,
                    'message': message
                })
                phone_numbers.append(reservation.phone)

            # Send bulk SMS (from line 86-124)
            logger.info(f"Sending {len(messages)} SMS messages for campaign '{tag}'")

            result = await self.sms_provider.send_bulk(messages)

            if result.get('success'):
                campaign.sent_count = len(messages)

                # Mark as sent (from line 38-57)
                for reservation in targets:
                    if sms_type == 'room':
                        reservation.room_sms_sent = True
                        reservation.room_sms_sent_at = datetime.utcnow()
                    elif sms_type == 'party':
                        reservation.party_sms_sent = True
                        reservation.party_sms_sent_at = datetime.utcnow()

                logger.info(f"Campaign successful: {campaign.sent_count} messages sent")

            else:
                campaign.failed_count = len(messages)
                campaign.error_message = result.get('error', 'Unknown error')
                logger.error(f"Campaign failed: {campaign.error_message}")

            campaign.completed_at = datetime.utcnow()
            self.db.add(campaign)
            self.db.commit()

            return campaign

        except Exception as e:
            logger.error(f"Error executing campaign: {e}")
            campaign.error_message = str(e)
            campaign.completed_at = datetime.utcnow()
            self.db.add(campaign)
            self.db.commit()
            raise

    def get_campaign_stats(self, campaign_id: int) -> Dict[str, Any]:
        """Get campaign statistics"""
        campaign = self.db.query(CampaignLog).filter_by(id=campaign_id).first()
        if not campaign:
            return {}

        return {
            'id': campaign.id,
            'type': campaign.campaign_type,
            'tag': campaign.target_tag,
            'target_count': campaign.target_count,
            'sent_count': campaign.sent_count,
            'failed_count': campaign.failed_count,
            'sent_at': campaign.sent_at.isoformat() if campaign.sent_at else None,
            'completed_at': campaign.completed_at.isoformat() if campaign.completed_at else None
        }
