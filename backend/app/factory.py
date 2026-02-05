"""
Provider factory for hot-swapping Mock and Real implementations.
This is the CRITICAL file for demo/production mode switching.
"""
from app.config import settings
from app.providers.base import SMSProvider, ReservationProvider, LLMProvider, StorageProvider
import logging

logger = logging.getLogger(__name__)


def get_sms_provider() -> SMSProvider:
    """Get SMS provider based on DEMO_MODE"""
    if settings.DEMO_MODE:
        logger.info("🎭 Using MockSMSProvider (DEMO_MODE=true)")
        from app.mock.sms import MockSMSProvider
        return MockSMSProvider()
    else:
        logger.info("🚀 Using RealSMSProvider (DEMO_MODE=false)")
        from app.real.sms import RealSMSProvider
        return RealSMSProvider(
            api_key=settings.SMS_API_KEY, api_secret=settings.SMS_API_SECRET
        )


def get_reservation_provider() -> ReservationProvider:
    """Get reservation provider based on DEMO_MODE"""
    if settings.DEMO_MODE:
        logger.info("🎭 Using MockReservationProvider (DEMO_MODE=true)")
        from app.mock.reservation import MockReservationProvider
        return MockReservationProvider()
    else:
        logger.info("🚀 Using RealReservationProvider (DEMO_MODE=false)")
        from app.real.reservation import RealReservationProvider
        return RealReservationProvider(
            email=settings.NAVER_RESERVATION_EMAIL,
            password=settings.NAVER_RESERVATION_PASSWORD,
        )


def get_llm_provider() -> LLMProvider:
    """Get LLM provider based on DEMO_MODE"""
    if settings.DEMO_MODE:
        logger.info("🎭 Using MockLLMProvider (DEMO_MODE=true)")
        from app.mock.llm import MockLLMProvider
        return MockLLMProvider()
    else:
        logger.info("🚀 Using RealLLMProvider (DEMO_MODE=false)")
        from app.real.llm import RealLLMProvider
        return RealLLMProvider(api_key=settings.CLAUDE_API_KEY)


def get_storage_provider() -> StorageProvider:
    """Get storage provider based on DEMO_MODE"""
    if settings.DEMO_MODE:
        logger.info("🎭 Using MockStorageProvider (DEMO_MODE=true)")
        from app.mock.storage import MockStorageProvider
        return MockStorageProvider()
    else:
        logger.info("🚀 Using RealStorageProvider (DEMO_MODE=false)")
        from app.real.storage import RealStorageProvider
        return RealStorageProvider(credentials_path=settings.GOOGLE_SHEETS_CREDENTIALS)
