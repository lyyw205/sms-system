"""
Template Renderer - Dynamic message generation with variable substitution
Ported from stable-clasp-main/function_replaceMessage.js and password generation
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import re
import logging

from app.db.models import MessageTemplate
from app.diag_logger import diag

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
        template = self.get_template(template_key)

        if not template:
            diag("template.render.enter", level="verbose", template_key=template_key)
            logger.error(f"Template '{template_key}' not found")
            diag(
                "template.render.exit",
                level="verbose",
                template_key=template_key,
                length=0,
                unreplaced_count=0,
                found=False,
            )
            return f"[Template '{template_key}' not found]"

        return self.render_content(template, variables)

    def render_content(self, template: MessageTemplate, variables: Dict[str, Any]) -> str:
        """
        이미 로드된 MessageTemplate 객체를 렌더링 (DB 재조회 없음).

        render() 와 동일한 치환/미치환/diag 경로를 공유한다. 호출자가 이미
        get_template() 으로 로드한 객체를 넘기면 template 재조회를 피할 수 있다
        (Tier1 egress fix 3: SMS 1건당 message_templates 2회 조회 → 1회).
        diag 시퀀스(enter → [unreplaced] → exit)는 render() 의 found 경로와 완전히 동일.
        """
        template_key = template.template_key
        diag("template.render.enter", level="verbose", template_key=template_key)

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
            diag(
                "template.render.unreplaced",
                level="critical",
                template_key=template_key,
                unreplaced=list(unreplaced)[:5],
            )

        diag(
            "template.render.exit",
            level="verbose",
            template_key=template_key,
            length=len(result),
            unreplaced_count=len(unreplaced),
        )

        return result

    def get_template(self, template_key: str) -> Optional[MessageTemplate]:
        """Get template by key"""
        return self.db.query(MessageTemplate).filter_by(
            template_key=template_key,
            is_active=True
        ).first()

