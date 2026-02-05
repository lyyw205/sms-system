"""
Real LLM Provider stub - to be implemented after contract
"""
from typing import Dict, Any, Optional


class RealLLMProvider:
    """Real LLM provider using Claude API + RAG"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_response(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate response using Claude API + RAG (ChromaDB)

        Implementation TODO:
        1. Query ChromaDB for relevant documents
        2. Build prompt with RAG context
        3. Call Claude API
        4. Parse response and calculate confidence

        Implementation time: ~3 hours
        """
        raise NotImplementedError("Real LLM provider not implemented yet")
