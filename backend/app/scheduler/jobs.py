"""
APScheduler jobs for automated SMS sending
Ported from stable-clasp-main/03_trigger.js
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from ..db.database import SessionLocal
from ..factory import get_reservation_provider, get_sms_provider, get_storage_provider
from ..notifications.service import NotificationService
from ..analytics.gender_analyzer import GenderAnalyzer

logger = logging.getLogger(__name__)

# Create scheduler instance
scheduler = AsyncIOScheduler()


async def sync_naver_reservations_job():
    """
    Sync reservations from Naver Booking API
    Runs every 10 minutes from 10:10 to 21:59

    Ported from: stable-clasp-main/03_trigger.js:1-16 (processTodayAuto - first part)
    """
    logger.info("Running Naver reservations sync job")

    db = SessionLocal()
    try:
        reservation_provider = get_reservation_provider()

        # Sync today's reservations
        today = datetime.now()
        reservations = await reservation_provider.sync_reservations(today)

        logger.info(f"Synced {len(reservations)} reservations from Naver")

        # Store in database
        from ..db.models import Reservation

        for res_data in reservations:
            # Check if already exists
            existing = db.query(Reservation).filter_by(
                naver_booking_id=res_data.get('naver_booking_id')
            ).first()

            if existing:
                # Update existing
                for key, value in res_data.items():
                    if hasattr(existing, key) and key != 'id':
                        setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
            else:
                # Create new
                reservation = Reservation(**res_data)
                db.add(reservation)

        db.commit()
        logger.info("Reservation sync completed successfully")

    except Exception as e:
        logger.error(f"Error in reservation sync job: {e}")
        db.rollback()
    finally:
        db.close()


async def send_party_guide_job():
    """
    Send party guide to unassigned guests
    Runs hourly from 12:10 to 21:59

    Ported from: stable-clasp-main/03_trigger.js:18-23 (processTodayAuto - second part)
    """
    logger.info("Running party guide job")

    db = SessionLocal()
    try:
        sms_provider = get_sms_provider()
        storage_provider = get_storage_provider()

        notification_service = NotificationService(db, sms_provider, storage_provider)

        # Send party guide for unassigned guests (rows 100-117)
        # These are guests without room assignments
        today = datetime.now()

        campaign = await notification_service.send_party_guide(
            date=today,
            start_row=100,  # Unassigned start
            end_row=117     # Unassigned end
        )

        logger.info(f"Party guide job completed: {campaign.sent_count} sent")

    except Exception as e:
        logger.error(f"Error in party guide job: {e}")
        db.rollback()
    finally:
        db.close()


async def extract_gender_stats_job():
    """
    Extract gender statistics from Google Sheets
    Runs every hour during party hours
    """
    logger.info("Running gender stats extraction job")

    db = SessionLocal()
    try:
        storage_provider = get_storage_provider()
        analyzer = GenderAnalyzer(db, storage_provider)

        today = datetime.now()
        stat = await analyzer.extract_gender_stats(today)

        if stat:
            logger.info(f"Gender stats extracted: M={stat.male_count}, F={stat.female_count}")

            # Log balance analysis
            balance = analyzer.calculate_party_balance(stat)
            logger.info(f"Party balance: {balance['recommendation']}")
        else:
            logger.warning("No gender stats extracted")

    except Exception as e:
        logger.error(f"Error in gender stats job: {e}")
    finally:
        db.close()


def setup_scheduler():
    """
    Setup all scheduled jobs

    Schedule based on stable-clasp-main/03_trigger.js:
    - Naver sync: Every 10 min, 10:10-21:59
    - Party guide: Every hour, 12:10-21:59
    - Gender stats: Every hour, 10:00-22:00
    """
    # Naver reservations sync - every 10 minutes from 10:10 to 21:59
    # Ported from line 6-16
    scheduler.add_job(
        sync_naver_reservations_job,
        trigger=CronTrigger(
            hour='10-21',
            minute='*/10',
            timezone='Asia/Seoul'
        ),
        id='sync_naver_reservations',
        name='Sync Naver Reservations',
        replace_existing=True
    )

    # Party guide - hourly from 12:00 to 21:00
    # Ported from line 18-23
    scheduler.add_job(
        send_party_guide_job,
        trigger=CronTrigger(
            hour='12-21',
            minute='10',
            timezone='Asia/Seoul'
        ),
        id='send_party_guide',
        name='Send Party Guide',
        replace_existing=True
    )

    # Gender stats extraction - hourly
    scheduler.add_job(
        extract_gender_stats_job,
        trigger=CronTrigger(
            hour='10-22',
            minute='0',
            timezone='Asia/Seoul'
        ),
        id='extract_gender_stats',
        name='Extract Gender Stats',
        replace_existing=True
    )

    logger.info("Scheduler jobs configured")


def start_scheduler():
    """Start the scheduler"""
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")


def get_job_info():
    """Get information about scheduled jobs"""
    jobs = scheduler.get_jobs()
    return [
        {
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        }
        for job in jobs
    ]
