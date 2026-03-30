"""
Template Renderer - Dynamic message generation with variable substitution
Ported from stable-clasp-main/function_replaceMessage.js and password generation
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import re
import logging

from app.db.models import MessageTemplate

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """
    Renders message templates with variable substitution

    Ported from: stable-clasp-main/function_replaceMessage.js
    """

    def __init__(self, db: Session):
        self.db = db

    def render(self, template_key: str, variables: Dict[str, Any]) -> str:
        """
        Render template with variable substitution

        Args:
            template_key: Template key to look up
            variables: Dictionary of variables to substitute

        Returns:
            Rendered message string

        Ported from: stable-clasp-main/function_replaceMessage.js
        """
        # Get template from database
        template = self.db.query(MessageTemplate).filter_by(
            template_key=template_key,
            is_active=True
        ).first()

        if not template:
            logger.error(f"Template '{template_key}' not found")
            return f"[Template '{template_key}' not found]"

        # Start with template content
        result = template.content

        # Replace variables (format: {{variableName}})
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))

        # Check for unreplaced variables (undefined detection)
        unreplaced = re.findall(r'\{\{(\w+)\}\}', result)
        if unreplaced:
            logger.warning(f"Undefined variables in template '{template_key}': {unreplaced}")

        return result

    def get_template(self, template_key: str) -> Optional[MessageTemplate]:
        """Get template by key"""
        return self.db.query(MessageTemplate).filter_by(
            template_key=template_key,
            is_active=True
        ).first()

