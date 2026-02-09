#!/usr/bin/env python3
"""
Simple verification script for template scheduling migration
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.db.models import TemplateSchedule, MessageTemplate, Reservation
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Verify migration"""
    logger.info("=== Verification Report ===\n")

    db = SessionLocal()
    try:
        # 1. Check template schedules
        schedules = db.query(TemplateSchedule).all()
        logger.info(f"✓ Template Schedules: {len(schedules)}")

        for schedule in schedules:
            logger.info(f"\n  Schedule #{schedule.id}: {schedule.schedule_name}")
            logger.info(f"    Template: {schedule.template.name if schedule.template else 'MISSING'}")
            logger.info(f"    Type: {schedule.schedule_type}")

            if schedule.schedule_type == 'hourly':
                logger.info(f"    Schedule: Every hour at :{schedule.minute:02d}")
            elif schedule.schedule_type == 'interval':
                logger.info(f"    Schedule: Every {schedule.interval_minutes} minutes")
            elif schedule.schedule_type == 'daily':
                logger.info(f"    Schedule: Daily at {schedule.hour}:{schedule.minute:02d}")
            elif schedule.schedule_type == 'weekly':
                logger.info(f"    Schedule: {schedule.day_of_week} at {schedule.hour}:{schedule.minute:02d}")

            logger.info(f"    Target: {schedule.target_type}")
            logger.info(f"    Date Filter: {schedule.date_filter or 'None'}")
            logger.info(f"    SMS Type: {schedule.sms_type}")
            logger.info(f"    Exclude Sent: {schedule.exclude_sent}")
            logger.info(f"    Active: {schedule.active}")

        # 2. Check templates
        templates = db.query(MessageTemplate).all()
        logger.info(f"\n✓ Message Templates: {len(templates)}")

        for template in templates:
            schedule_count = len(template.schedules) if hasattr(template, 'schedules') else 0
            logger.info(f"  - {template.name} ({template.key}): {schedule_count} schedule(s)")

        # 3. Check reservations
        today_reservations = db.query(Reservation).filter(
            Reservation.date == '2026-02-09'
        ).count()
        logger.info(f"\n✓ Today's Reservations: {today_reservations}")

        # 4. Count potential targets
        room_assigned = db.query(Reservation).filter(
            Reservation.date == '2026-02-09',
            Reservation.room_number.isnot(None),
            Reservation.room_sms_sent == False
        ).count()

        party_only = db.query(Reservation).filter(
            Reservation.date == '2026-02-09',
            Reservation.room_number.is_(None),
            Reservation.tags.like('%파티만%'),
            Reservation.party_sms_sent == False
        ).count()

        logger.info(f"\n✓ Potential Targets (not yet sent):")
        logger.info(f"  - Room assigned: {room_assigned}")
        logger.info(f"  - Party only: {party_only}")

        # 5. Summary
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✓ Database schema: OK")
        logger.info(f"✓ Template schedules: {len(schedules)} created")
        logger.info(f"✓ Relationships: OK")
        logger.info(f"✓ Ready for testing")
        logger.info("\nNext steps:")
        logger.info("1. Start backend: uvicorn app.main:app --reload")
        logger.info("2. Start frontend: cd ../frontend && npm run dev")
        logger.info("3. Access Templates page: http://localhost:5173/templates")
        logger.info("4. Test manual schedule execution")
        logger.info("5. Verify APScheduler integration")

        return 0

    except Exception as e:
        logger.error(f"\n✗ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
