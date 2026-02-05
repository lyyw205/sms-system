"""
Real Storage Provider stub - to be implemented after contract
"""
from typing import List, Dict, Any


class RealStorageProvider:
    """Real storage provider using Google Sheets API"""

    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path

    async def sync_to_storage(self, data: List[Dict[str, Any]], sheet_name: str) -> bool:
        """
        Export data to Google Sheets

        Implementation TODO:
        1. Load service account credentials
        2. Use gspread library
        3. Find or create spreadsheet
        4. Update sheet with data

        Implementation time: ~1 hour
        """
        raise NotImplementedError("Real storage provider not implemented yet")

    async def sync_from_storage(self, sheet_name: str) -> List[Dict[str, Any]]:
        """
        Import data from Google Sheets

        Implementation TODO:
        1. Read data from specified sheet
        2. Parse and return as list of dicts

        Implementation time: ~30 min
        """
        raise NotImplementedError("Real storage provider not implemented yet")
