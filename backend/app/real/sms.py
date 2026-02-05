"""
Real SMS Provider stub - to be implemented after contract
"""
from typing import Dict, Any


class RealSMSProvider:
    """Real SMS provider using NHN Cloud API (stub)"""

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    async def send_sms(self, to: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send actual SMS via NHN Cloud API"""
        # TODO: Implement actual SMS sending
        # Implementation time: ~1 hour
        raise NotImplementedError("Real SMS provider not implemented yet")

    async def simulate_receive(self, from_: str, to: str, message: str) -> Dict[str, Any]:
        """This method not used in production (webhook handles it)"""
        raise NotImplementedError("Use webhook endpoint in production")
