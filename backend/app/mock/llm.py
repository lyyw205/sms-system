"""
Mock LLM Provider for demo mode.
Uses predefined Q&A database with keyword matching.
"""
import logging
from typing import Dict, Any, Optional
import random

logger = logging.getLogger(__name__)


class MockLLMProvider:
    """Mock LLM provider with predefined Q&A"""

    def __init__(self):
        # Predefined Q&A database based on common customer queries
        self.qa_database = {
            "할인": {
                "response": "현재 진행 중인 할인 행사는 없습니다. 추후 이벤트 정보는 문자로 안내드리겠습니다.",
                "confidence": 0.70,
            },
            "취소": {
                "response": "예약 취소는 1일 전까지 가능합니다. 고객센터로 연락 주세요.",
                "confidence": 0.75,
            },
            "변경": {
                "response": "예약 변경은 고객센터(010-9999-0000)로 연락 부탁드립니다.",
                "confidence": 0.78,
            },
            "결제": {
                "response": "결제는 현장 결제 또는 계좌이체 가능합니다.",
                "confidence": 0.72,
            },
            "카드": {
                "response": "신용카드 결제 가능합니다.",
                "confidence": 0.80,
            },
            "환불": {
                "response": "환불은 예약 취소 시 자동으로 처리됩니다.",
                "confidence": 0.68,
            },
            "준비물": {
                "response": "방문 시 신분증을 지참해 주세요.",
                "confidence": 0.85,
            },
            "소요시간": {
                "response": "서비스는 약 1시간 소요됩니다.",
                "confidence": 0.82,
            },
            "주말": {
                "response": "주말에도 영업합니다. 10:00-17:00 영업합니다.",
                "confidence": 0.88,
            },
            "공휴일": {
                "response": "공휴일은 휴무입니다.",
                "confidence": 0.90,
            },
        }

        # Generic fallback responses for unknown queries
        self.fallback_responses = [
            "죄송합니다. 정확한 답변을 드리기 어렵습니다. 고객센터(010-9999-0000)로 연락 주세요.",
            "자세한 상담은 전화 또는 방문 상담을 권장드립니다.",
            "문의 내용을 확인 후 답변드리겠습니다.",
        ]

    async def generate_response(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate response using keyword matching.
        Returns: {
            "response": str,
            "confidence": float (0-1),
            "needs_review": bool
        }
        """
        logger.info(f"🤖 [MOCK LLM] Generating response for: '{message}'")

        # Try keyword matching
        for keyword, qa in self.qa_database.items():
            if keyword in message:
                confidence = qa["confidence"] + random.uniform(-0.05, 0.05)  # Add variance
                needs_review = confidence < 0.6

                logger.info(
                    f"   Matched keyword: '{keyword}'\n"
                    f"   Response: '{qa['response']}'\n"
                    f"   Confidence: {confidence:.2f}\n"
                    f"   Needs Review: {needs_review}\n"
                    f"   ⚠️  In production mode, Claude API will generate this"
                )

                return {
                    "response": qa["response"],
                    "confidence": confidence,
                    "needs_review": needs_review,
                    "source": "llm",
                }

        # No keyword match - return fallback with low confidence
        fallback = random.choice(self.fallback_responses)
        confidence = random.uniform(0.30, 0.50)
        needs_review = True

        logger.info(
            f"   No keyword match - using fallback\n"
            f"   Response: '{fallback}'\n"
            f"   Confidence: {confidence:.2f}\n"
            f"   Needs Review: {needs_review}\n"
            f"   ⚠️  In production mode, Claude API with RAG will handle this"
        )

        return {
            "response": fallback,
            "confidence": confidence,
            "needs_review": needs_review,
            "source": "llm",
        }
