"""
Message routing logic: Rules → LLM fallback → Human-in-the-Loop
"""
from app.rules.engine import RuleEngine
from app.factory import get_llm_provider
from typing import Dict, Any, List, Optional
import re
import logging

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes messages through rule engine → LLM → human review"""

    def __init__(self):
        self.rule_engine = RuleEngine()

    async def generate_auto_response(self, message: str, rules: Optional[List] = None) -> Dict[str, Any]:
        """
        Generate auto-response for incoming message.
        If rules (list of Rule ORM objects) is provided, use them for matching.
        Otherwise fall back to the YAML-based rule engine.
        Returns: {
            "response": str,
            "confidence": float,
            "needs_review": bool,
            "source": str (rule/llm)
        }
        """
        logger.info(f"📨 Routing message: '{message}'")

        # Step 1: Try DB rules if provided
        if rules is not None:
            for rule in rules:
                if rule.is_active and re.search(rule.pattern, message, re.IGNORECASE):
                    logger.info(f"✅ DB rule matched (id={rule.id})! Confidence: 0.95")
                    return {
                        "response": rule.response,
                        "confidence": 0.95,
                        "needs_review": False,
                        "source": "rule",
                    }
        else:
            # Fall back to YAML rule engine
            rule_result = self.rule_engine.match(message)
            if rule_result:
                logger.info(f"✅ Rule matched! Confidence: {rule_result['confidence']:.2f}")
                return rule_result

        # Step 2: Fallback to LLM
        logger.info("⚠️  No rule matched, falling back to LLM...")
        llm_provider = get_llm_provider()
        llm_result = await llm_provider.generate_response(message)

        # Step 3: Check if needs human review
        if llm_result["needs_review"]:
            logger.warning(
                f"🚨 Low confidence ({llm_result['confidence']:.2f}) - "
                "message queued for human review"
            )

        return llm_result

    def reload_rules(self):
        """Hot reload rules (YAML-based engine)"""
        self.rule_engine.reload_rules()
