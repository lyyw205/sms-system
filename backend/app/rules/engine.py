"""
Rule-based response engine with regex pattern matching
"""
import re
import yaml
from typing import Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class RuleEngine:
    """Rule-based auto-response engine"""

    def __init__(self, rules_file: str = "app/rules/rules.yaml"):
        self.rules_file = Path(rules_file)
        self.rules = []
        self.load_rules()

    def load_rules(self):
        """Load rules from YAML file"""
        try:
            with open(self.rules_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.rules = data.get("rules", [])
                # Sort by priority (descending)
                self.rules.sort(key=lambda x: x.get("priority", 0), reverse=True)
                logger.info(f"Loaded {len(self.rules)} rules from {self.rules_file}")
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
            self.rules = []

    def reload_rules(self):
        """Hot reload rules from file"""
        logger.info("Reloading rules...")
        self.load_rules()

    def match(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Match message against rules.
        Returns: {
            "response": str,
            "confidence": float,
            "rule_name": str,
            "needs_review": bool
        } or None if no match
        """
        for rule in self.rules:
            if not rule.get("active", True):
                continue

            pattern = rule.get("pattern", "")
            try:
                if re.search(pattern, message, re.IGNORECASE):
                    logger.info(
                        f"✅ Rule matched: '{rule.get('name')}' for message: '{message}'"
                    )
                    return {
                        "response": rule.get("response", ""),
                        "confidence": 0.95,  # High confidence for rule-based
                        "rule_name": rule.get("name"),
                        "needs_review": False,
                        "source": "rule",
                    }
            except re.error as e:
                logger.error(f"Invalid regex pattern in rule '{rule.get('name')}': {e}")
                continue

        logger.info(f"❌ No rule matched for message: '{message}'")
        return None
