"""
Mock LLM Provider for demo mode.
Uses keyword matching instead of actual Claude API calls.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Simple keyword-response mapping for demo
KEYWORD_RESPONSES = {
    "영업시간": "영업시간은 오전 10시부터 오후 10시까지입니다.",
    "위치": "서울시 강남구에 위치하고 있습니다.",
    "주차": "건물 지하 주차장을 이용하실 수 있습니다.",
    "예약": "예약은 네이버 예약 또는 전화로 가능합니다.",
    "가격": "자세한 가격은 네이버 예약 페이지를 참고해주세요.",
    "취소": "예약 취소는 체크인 24시간 전까지 가능합니다.",
}


class MockLLMProvider:
    """Mock LLM provider - keyword matching instead of Claude API"""

    async def generate_response(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate response using keyword matching."""
        logger.info(f"[MOCK LLM] Generating response for: '{message}'")

        # Check keywords
        for keyword, response in KEYWORD_RESPONSES.items():
            if keyword in message:
                logger.info(f"[MOCK LLM] Keyword matched: '{keyword}'")
                return {
                    "response": response,
                    "confidence": 0.75,
                    "needs_review": False,
                    "source": "llm",
                }

        # No keyword match — low confidence, needs human review
        logger.info("[MOCK LLM] No keyword matched, flagging for review")
        return {
            "response": "죄송합니다, 해당 문의에 대한 답변을 준비 중입니다. 잠시만 기다려주세요.",
            "confidence": 0.3,
            "needs_review": True,
            "source": "llm",
        }
