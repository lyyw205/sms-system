"""
Template-based schedule execution engine
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from app.db.models import TemplateSchedule, Reservation, CampaignLog
from app.db.database import get_db
from app.factory import get_sms_provider
from app.templates.renderer import TemplateRenderer

logger = logging.getLogger(__name__)


class TemplateScheduleExecutor:
    """Execute template-based scheduled messages"""

    def __init__(self, db: Session):
        self.db = db
        self.sms_provider = get_sms_provider()
        self.template_renderer = TemplateRenderer()

    async def execute_schedule(self, schedule_id: int) -> Dict[str, Any]:
        """
        Execute a template schedule

        Steps:
        1. Load TemplateSchedule
        2. Filter targets based on configuration
        3. Render template for each target
        4. Send SMS (bulk)
        5. Update tracking flags
        6. Log campaign

        Returns:
            Dict with execution results
        """
        logger.info(f"Executing template schedule #{schedule_id}")

        # Load schedule
        schedule = self.db.query(TemplateSchedule).filter(
            TemplateSchedule.id == schedule_id,
            TemplateSchedule.active == True
        ).first()

        if not schedule:
            logger.warning(f"Schedule #{schedule_id} not found or inactive")
            return {"success": False, "error": "Schedule not found or inactive"}

        if not schedule.template or not schedule.template.active:
            logger.warning(f"Template for schedule #{schedule_id} not found or inactive")
            return {"success": False, "error": "Template not found or inactive"}

        try:
            # Get targets
            targets = self.get_targets(schedule)
            logger.info(f"Found {len(targets)} targets for schedule #{schedule_id}")

            if not targets:
                # Update last_run even if no targets
                schedule.last_run = datetime.utcnow()
                self.db.commit()
                return {"success": True, "sent_count": 0, "message": "No targets found"}

            # Create campaign log
            campaign_log = CampaignLog(
                campaign_type=f"template_schedule_{schedule.schedule_name}",
                target_tag=schedule.target_value if schedule.target_type == 'tag' else None,
                target_count=len(targets),
                sent_count=0,
                failed_count=0
            )
            self.db.add(campaign_log)
            self.db.commit()

            # Send messages
            sent_count = 0
            failed_count = 0

            for reservation in targets:
                try:
                    # Render template with reservation data
                    context = self._build_template_context(reservation)
                    message_content = self.template_renderer.render(
                        schedule.template.key,
                        context
                    )

                    # Send SMS
                    result = await self.sms_provider.send_sms(
                        to=reservation.phone,
                        message=message_content
                    )

                    if result.get('success'):
                        sent_count += 1

                        # Update tracking flags
                        if schedule.sms_type == 'room':
                            reservation.room_sms_sent = True
                            reservation.room_sms_sent_at = datetime.utcnow()
                        elif schedule.sms_type == 'party':
                            reservation.party_sms_sent = True
                            reservation.party_sms_sent_at = datetime.utcnow()

                        # Update sent_sms_types
                        sent_types = reservation.sent_sms_types or ""
                        if schedule.template.category not in sent_types:
                            reservation.sent_sms_types = f"{sent_types},{schedule.template.category}" if sent_types else schedule.template.category

                        self.db.commit()
                        logger.info(f"Sent SMS to {reservation.customer_name} ({reservation.phone})")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to send SMS to {reservation.phone}: {result.get('error')}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error sending SMS to reservation #{reservation.id}: {str(e)}")

            # Update campaign log
            campaign_log.sent_count = sent_count
            campaign_log.failed_count = failed_count
            campaign_log.completed_at = datetime.utcnow()

            # Update schedule
            schedule.last_run = datetime.utcnow()

            self.db.commit()

            logger.info(f"Schedule #{schedule_id} execution completed: {sent_count} sent, {failed_count} failed")

            return {
                "success": True,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "target_count": len(targets)
            }

        except Exception as e:
            logger.error(f"Error executing schedule #{schedule_id}: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def get_targets(self, schedule: TemplateSchedule) -> List[Reservation]:
        """
        Filter targets based on schedule configuration

        Args:
            schedule: TemplateSchedule instance

        Returns:
            List of Reservation instances
        """
        query = self.db.query(Reservation).filter(
            Reservation.status == 'confirmed'
        )

        # Apply date filter
        if schedule.date_filter:
            target_date = self._parse_date_filter(schedule.date_filter)
            if target_date:
                query = query.filter(Reservation.date == target_date)

        # Apply target type filter
        if schedule.target_type == 'all':
            # All reservations (no additional filter)
            pass
        elif schedule.target_type == 'tag':
            # Specific tag
            if schedule.target_value:
                query = query.filter(Reservation.tags.like(f'%{schedule.target_value}%'))
        elif schedule.target_type == 'room_assigned':
            # Has room number
            query = query.filter(Reservation.room_number.isnot(None))
        elif schedule.target_type == 'party_only':
            # No room number AND has '파티만' tag
            query = query.filter(
                Reservation.room_number.is_(None),
                Reservation.tags.like('%파티만%')
            )

        # Apply exclude_sent filter
        if schedule.exclude_sent:
            if schedule.sms_type == 'room':
                query = query.filter(Reservation.room_sms_sent == False)
            elif schedule.sms_type == 'party':
                query = query.filter(Reservation.party_sms_sent == False)

        return query.all()

    def preview_targets(self, schedule: TemplateSchedule) -> List[Dict[str, Any]]:
        """
        Preview targets without sending messages

        Returns:
            List of target information dicts
        """
        targets = self.get_targets(schedule)

        return [
            {
                "id": r.id,
                "customer_name": r.customer_name,
                "phone": r.phone,
                "date": r.date,
                "time": r.time,
                "room_number": r.room_number,
                "tags": r.tags,
                "room_sms_sent": r.room_sms_sent,
                "party_sms_sent": r.party_sms_sent
            }
            for r in targets
        ]

    def _parse_date_filter(self, date_filter: str) -> str:
        """
        Parse date filter to YYYY-MM-DD format

        Args:
            date_filter: 'today', 'tomorrow', or 'YYYY-MM-DD'

        Returns:
            Date string in YYYY-MM-DD format or None
        """
        if date_filter == 'today':
            return date.today().strftime('%Y-%m-%d')
        elif date_filter == 'tomorrow':
            return (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        elif date_filter and len(date_filter) == 10:  # YYYY-MM-DD
            return date_filter
        return None

    def _build_template_context(self, reservation: Reservation) -> Dict[str, Any]:
        """
        Build template rendering context from reservation

        Args:
            reservation: Reservation instance

        Returns:
            Context dict with all available variables
        """
        # Parse room number for building/room
        building = ""
        room_num = ""
        if reservation.room_number:
            if len(reservation.room_number) >= 4:
                building = reservation.room_number[0]
                room_num = reservation.room_number[1:]
            else:
                room_num = reservation.room_number

        return {
            "customerName": reservation.customer_name,
            "name": reservation.customer_name,  # Alias
            "phone": reservation.phone,
            "date": reservation.date,
            "time": reservation.time,
            "roomNumber": reservation.room_number or "",
            "building": building,
            "roomNum": room_num,
            "password": reservation.room_password or "",
            "tags": reservation.tags or "",
            "partyParticipants": reservation.party_participants or 0,
            "status": reservation.status
        }
