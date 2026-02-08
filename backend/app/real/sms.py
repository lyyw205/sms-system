"""
Real SMS Provider - Integration with existing SMS API
Ported from stable-clasp-main/00_main.js and 01_sns.js
"""
from typing import Dict, Any, List
import httpx
import logging

logger = logging.getLogger(__name__)


class RealSMSProvider:
    """Real SMS provider using existing SMS API at http://15.164.246.59:3000/sendMass"""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        """
        Initialize SMS provider

        Args:
            api_key: Not used currently (API endpoint doesn't require auth)
            api_secret: Not used currently
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_url = "http://15.164.246.59:3000/sendMass"

    async def send_sms(self, to: str, message: str, **kwargs) -> Dict[str, Any]:
        """
        Send single SMS message

        Args:
            to: Phone number (e.g., "01012345678")
            message: Message content
            **kwargs: Additional options (msg_type, testmode_yn)

        Returns:
            Response from API

        Ported from: stable-clasp-main/00_main.js (roomGuideInRange SMS logic)
        """
        msg_type = kwargs.get('msg_type', 'LMS')  # Default to LMS for long messages
        testmode = kwargs.get('testmode_yn', 'N')

        payload = {
            "msg_type": msg_type,
            "cnt": "1",
            "rec_1": to,
            "msg_1": message,
            "testmode_yn": testmode
        }

        return await self._send_bulk(payload)

    async def send_bulk(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Send bulk SMS messages

        Args:
            messages: List of dicts with 'to' and 'message' keys
            **kwargs: Additional options (msg_type, testmode_yn)

        Returns:
            Response from API

        Ported from: stable-clasp-main/01_sns.js:86-124 (sendSmsAndMark)
        """
        if not messages:
            logger.warning("No messages to send")
            return {"success": False, "error": "No messages provided"}

        msg_type = kwargs.get('msg_type', 'LMS')
        testmode = kwargs.get('testmode_yn', 'N')

        # Build payload for bulk sending
        # Format from line 86-95 of 01_sns.js
        payload = {
            "msg_type": msg_type,
            "cnt": str(len(messages)),
            "testmode_yn": testmode
        }

        for i, msg in enumerate(messages, start=1):
            payload[f"rec_{i}"] = msg['to']
            payload[f"msg_{i}"] = msg['message']

        return await self._send_bulk(payload)

    async def _send_bulk(self, payload: Dict[str, str]) -> Dict[str, Any]:
        """
        Internal method to send bulk SMS via API

        Args:
            payload: Full payload dict with msg_type, cnt, rec_N, msg_N

        Returns:
            API response
        """
        try:
            logger.info(f"Sending {payload.get('cnt', 0)} SMS messages (testmode={payload.get('testmode_yn')})")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"SMS API response: {result}")

                return {
                    "success": True,
                    "count": int(payload.get('cnt', 0)),
                    "response": result
                }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending SMS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def simulate_receive(self, from_: str, to: str, message: str) -> Dict[str, Any]:
        """
        This method not used in production (webhook handles incoming messages)
        """
        raise NotImplementedError("Use webhook endpoint in production")
