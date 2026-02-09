#!/usr/bin/env python3
"""
Setup script for template scheduling system
1. Creates TemplateSchedule table (if not exists)
2. Migrates hardcoded schedules to template-based schedules
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import init_db
from app.db.migrate_templates import migrate_legacy_to_templates, SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run setup"""
    logger.info("=== Template Scheduling System Setup ===")

    # Step 1: Initialize database (creates TemplateSchedule table)
    logger.info("Step 1: Initializing database tables...")
    init_db()
    logger.info("✓ Database tables created/updated")

    # Step 2: Run migration to create default schedules
    logger.info("Step 2: Migrating legacy schedules to template-based schedules...")
    db = SessionLocal()
    try:
        migrate_legacy_to_templates(db)
        logger.info("✓ Migration completed successfully")
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        return 1
    finally:
        db.close()

    logger.info("\n=== Setup Complete ===")
    logger.info("The template scheduling system is now ready.")
    logger.info("You can access it at: http://localhost:5173/templates")
    logger.info("\nNext steps:")
    logger.info("1. Start the backend: cd backend && uvicorn app.main:app --reload")
    logger.info("2. Start the frontend: cd frontend && npm run dev")
    logger.info("3. Navigate to Templates page to manage schedules")

    return 0


if __name__ == "__main__":
    sys.exit(main())
