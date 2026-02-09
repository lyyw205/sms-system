"""
Migration script to create default template schedules
Replaces hardcoded send_party_guide_job with template-based schedules
"""
import logging
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import MessageTemplate, TemplateSchedule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_legacy_to_templates(db: Session):
    """
    Create default template schedules for party and room guides

    This migrates from hardcoded scheduler jobs to template-based schedules:
    1. Party guide: Hourly at 10 minutes (12:10-21:10)
    2. Room guide: Every 10 minutes
    """
    logger.info("Starting template schedule migration")

    # Check if party_guide template exists
    party_template = db.query(MessageTemplate).filter_by(key='party_guide').first()

    if party_template:
        # Check if schedule already exists
        existing_party_schedule = db.query(TemplateSchedule).filter_by(
            template_id=party_template.id,
            schedule_name="파티 안내 자동 발송"
        ).first()

        if not existing_party_schedule:
            # Create party guide schedule (hourly at 10 minutes, 12:10-21:10)
            party_schedule = TemplateSchedule(
                template_id=party_template.id,
                schedule_name="파티 안내 자동 발송",
                schedule_type="hourly",
                minute=10,
                timezone="Asia/Seoul",
                target_type="party_only",
                target_value=None,
                date_filter="today",
                sms_type="party",
                exclude_sent=True,
                active=True
            )
            db.add(party_schedule)
            logger.info("Created party guide schedule")
        else:
            logger.info("Party guide schedule already exists")
    else:
        logger.warning("party_guide template not found, skipping party schedule creation")

    # Check if room_guide template exists
    room_template = db.query(MessageTemplate).filter_by(key='room_guide').first()

    if room_template:
        # Check if schedule already exists
        existing_room_schedule = db.query(TemplateSchedule).filter_by(
            template_id=room_template.id,
            schedule_name="객실 안내 자동 발송"
        ).first()

        if not existing_room_schedule:
            # Create room guide schedule (every 10 minutes)
            room_schedule = TemplateSchedule(
                template_id=room_template.id,
                schedule_name="객실 안내 자동 발송",
                schedule_type="interval",
                interval_minutes=10,
                timezone="Asia/Seoul",
                target_type="room_assigned",
                target_value=None,
                date_filter="today",
                sms_type="room",
                exclude_sent=True,
                active=True
            )
            db.add(room_schedule)
            logger.info("Created room guide schedule")
        else:
            logger.info("Room guide schedule already exists")
    else:
        logger.warning("room_guide template not found, skipping room schedule creation")

    # Commit all changes
    db.commit()
    logger.info("Template schedule migration completed")


def main():
    """Run the migration"""
    db = SessionLocal()
    try:
        migrate_legacy_to_templates(db)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
