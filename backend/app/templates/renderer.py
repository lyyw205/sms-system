"""
Template Renderer - Dynamic message generation with variable substitution
Ported from stable-clasp-main/function_replaceMessage.js and password generation
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import random
import re
import logging

from ..db.models import MessageTemplate

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
            key=template_key,
            active=True
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

    @staticmethod
    def generate_room_password(room_number: str) -> str:
        """
        Generate room password based on room number

        Args:
            room_number: Room number (e.g., "A101", "B205")

        Returns:
            Generated password string

        Ported from: stable-clasp-main/00_main.js:106-121
        """
        if not room_number or len(room_number) < 2:
            logger.warning(f"Invalid room number: {room_number}")
            return "0000"

        try:
            # Extract building letter and room number
            letter = room_number[0].upper()
            number = int(room_number[1:])

            # Calculate base password (from line 110-114)
            if letter == 'A':
                password = number * 4
            elif letter == 'B':
                password = number * 5
            else:
                logger.warning(f"Unknown building letter: {letter}")
                return "0000"

            # Add random digit and leading zero (from line 117-120)
            random_digit = random.randint(0, 9)
            final_password = f"{random_digit}0{password}"

            logger.debug(f"Generated password for {room_number}: {final_password}")
            return final_password

        except Exception as e:
            logger.error(f"Error generating password for {room_number}: {e}")
            return "0000"

    def render_room_guide(self, reservation: Any) -> str:
        """
        Render room guide message

        Args:
            reservation: Reservation object

        Returns:
            Room guide message

        Ported from: stable-clasp-main/00_main.js:178-188
        """
        if not reservation.room_number:
            logger.warning(f"No room number for reservation {reservation.id}")
            return "[Room number not assigned]"

        # Generate password if not set
        if not reservation.room_password:
            reservation.room_password = self.generate_room_password(reservation.room_number)

        # Extract building and room number
        building = reservation.room_number[0]
        room_num = reservation.room_number[1:]

        # Build message (from line 178-188)
        message = f"""
금일 객실은 스테이블 {building}동 {room_num}호 - {reservation.room_info or ''}룸입니다.(비밀번호: {reservation.room_password}*)

무인 체크인이라서 바로 입실하시면 됩니다.
객실내에서(발코니포함) 음주, 흡연, 취식, 혼숙 절대 금지입니다.(적발시 벌금 10만원 또는 퇴실)

파티 참여 시 저녁 8시에 B동 1층 포차로 내려와 주시면 되세요.

차량번호 회신 반드시 해주시고, 주차는 아래 자주묻는질문 링크를 참고하여 타차량 통행 가능하도록 해주세요.
자주묻는질문: https://bit.ly/3Ej6P9A
""".strip()

        return message

    def get_template(self, template_key: str) -> Optional[MessageTemplate]:
        """Get template by key"""
        return self.db.query(MessageTemplate).filter_by(
            key=template_key,
            active=True
        ).first()

    def create_template(
        self,
        key: str,
        name: str,
        content: str,
        variables: Optional[list] = None,
        category: Optional[str] = None
    ) -> MessageTemplate:
        """Create new message template"""
        import json

        template = MessageTemplate(
            key=key,
            name=name,
            content=content,
            variables=json.dumps(variables) if variables else None,
            category=category,
            active=True
        )

        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        logger.info(f"Created template '{key}'")
        return template
