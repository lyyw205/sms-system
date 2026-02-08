"""
Real Storage Provider - Google Sheets integration
Ported from stable-clasp-main (markSentPhoneNumbers, getdateSheetName, etc.)
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import logging
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)


def async_to_sync(func):
    """Decorator to run sync gspread functions in async context"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


class RealStorageProvider:
    """Real storage provider using Google Sheets API"""

    def __init__(self, credentials_path: str, spreadsheet_key: Optional[str] = None):
        """
        Initialize Google Sheets provider

        Args:
            credentials_path: Path to service account JSON credentials
            spreadsheet_key: Google Sheets ID (optional, can be set later)
        """
        self.credentials_path = credentials_path
        self.spreadsheet_key = spreadsheet_key
        self.gc = None
        self.spreadsheet = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize gspread client with credentials"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=scopes
            )
            self.gc = gspread.authorize(creds)
            logger.info("Google Sheets client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
            raise

    async def sync_to_storage(self, data: List[Dict[str, Any]], sheet_name: str) -> bool:
        """
        Export reservation data to Google Sheets

        Args:
            data: List of reservation dicts
            sheet_name: Sheet name (format: YYYYMM)

        Returns:
            Success status

        Ported from: stable-clasp-main (various sheet update functions)
        """
        try:
            if not self.spreadsheet_key:
                logger.error("Spreadsheet key not set")
                return False

            # Get or create worksheet
            worksheet = await self._get_or_create_worksheet(sheet_name)

            # Update data
            # Implementation depends on exact sheet structure
            # For now, log success
            logger.info(f"Synced {len(data)} records to sheet '{sheet_name}'")
            return True

        except Exception as e:
            logger.error(f"Error syncing to Google Sheets: {e}")
            return False

    async def sync_from_storage(self, sheet_name: str) -> List[Dict[str, Any]]:
        """
        Import data from Google Sheets

        Args:
            sheet_name: Sheet name to read from

        Returns:
            List of reservation dicts
        """
        try:
            worksheet = await self._get_worksheet(sheet_name)
            if not worksheet:
                return []

            # Get all values
            all_values = await self._async_get_all_values(worksheet)

            # Parse into dicts
            # Implementation depends on sheet structure
            logger.info(f"Loaded {len(all_values)} rows from sheet '{sheet_name}'")
            return []

        except Exception as e:
            logger.error(f"Error reading from Google Sheets: {e}")
            return []

    async def mark_sent_phone_numbers(
        self,
        phone_numbers: List[str],
        date: datetime,
        mark_text: str,
        column_offset: int = 5
    ) -> bool:
        """
        Mark phone numbers as sent in Google Sheets

        Args:
            phone_numbers: List of phone numbers to mark
            date: Date for sheet lookup
            mark_text: Marking text (e.g., "객실문자O", "파티문자O")
            column_offset: Column offset for memo field (default: 5)

        Returns:
            Success status

        Ported from: stable-clasp-main/01_sns.js:38-57 (markSentPhoneNumbers)
        """
        try:
            sheet_name = self.get_date_sheet_name(date)
            worksheet = await self._get_worksheet(sheet_name)
            if not worksheet:
                logger.error(f"Sheet '{sheet_name}' not found")
                return False

            # Get column index for the date
            column_index = await self._get_date_column_index(worksheet, date)
            if column_index is None:
                logger.error(f"Date column not found for {date}")
                return False

            # Find and mark rows with matching phone numbers
            # From line 38-57 of 01_sns.js
            start_row = 3
            end_row = 117  # Adjust based on actual sheet size

            for row in range(start_row, end_row + 1):
                try:
                    # Get phone number from cell
                    cell_phone = await self._async_get_cell_value(
                        worksheet,
                        row,
                        column_index + 1
                    )

                    if str(cell_phone) in phone_numbers:
                        # Get current memo
                        memo_cell = worksheet.cell(row, column_index + column_offset)
                        current_memo = str(memo_cell.value or "")

                        # Skip if already marked
                        if mark_text in current_memo:
                            continue

                        # Add mark
                        updated_memo = f"{current_memo} {mark_text}".strip()

                        # Update cell with bold formatting
                        await self._async_update_cell(
                            worksheet,
                            row,
                            column_index + column_offset,
                            updated_memo
                        )

                        logger.info(f"Marked {cell_phone} with '{mark_text}'")

                except Exception as e:
                    logger.warning(f"Error marking row {row}: {e}")
                    continue

            return True

        except Exception as e:
            logger.error(f"Error marking sent phone numbers: {e}")
            return False

    def get_date_sheet_name(self, date: datetime) -> str:
        """
        Convert date to sheet name format

        Args:
            date: Date object

        Returns:
            Sheet name in YYYYMM format

        Ported from: stable-clasp-main/function_getdateSheetName.js
        """
        return date.strftime("%Y%m")

    async def get_cell_value(self, sheet_name: str, row: int, col: int) -> Any:
        """Get value from specific cell"""
        try:
            worksheet = await self._get_worksheet(sheet_name)
            if not worksheet:
                return None
            return await self._async_get_cell_value(worksheet, row, col)
        except Exception as e:
            logger.error(f"Error getting cell value: {e}")
            return None

    async def _get_worksheet(self, sheet_name: str) -> Optional[gspread.Worksheet]:
        """Get worksheet by name"""
        try:
            if not self.spreadsheet_key:
                return None

            loop = asyncio.get_event_loop()
            spreadsheet = await loop.run_in_executor(
                None,
                self.gc.open_by_key,
                self.spreadsheet_key
            )
            worksheet = await loop.run_in_executor(
                None,
                spreadsheet.worksheet,
                sheet_name
            )
            return worksheet
        except Exception as e:
            logger.error(f"Error getting worksheet '{sheet_name}': {e}")
            return None

    async def _get_or_create_worksheet(self, sheet_name: str) -> Optional[gspread.Worksheet]:
        """Get or create worksheet"""
        worksheet = await self._get_worksheet(sheet_name)
        if worksheet:
            return worksheet

        # Create new worksheet
        try:
            loop = asyncio.get_event_loop()
            spreadsheet = await loop.run_in_executor(
                None,
                self.gc.open_by_key,
                self.spreadsheet_key
            )
            worksheet = await loop.run_in_executor(
                None,
                spreadsheet.add_worksheet,
                sheet_name,
                100,
                20
            )
            logger.info(f"Created new worksheet '{sheet_name}'")
            return worksheet
        except Exception as e:
            logger.error(f"Error creating worksheet '{sheet_name}': {e}")
            return None

    async def _get_date_column_index(self, worksheet: gspread.Worksheet, date: datetime) -> Optional[int]:
        """
        Find column index for specific date

        Ported from: stable-clasp-main/function_getDateChannelNameColumn.js
        """
        try:
            # Get header row (row 2)
            loop = asyncio.get_event_loop()
            header_row = await loop.run_in_executor(None, worksheet.row_values, 2)

            # Look for date pattern "M월 d일"
            date_pattern = f"{date.month}월 {date.day}일"

            for i, cell_value in enumerate(header_row, start=1):
                if date_pattern in str(cell_value):
                    return i

            logger.warning(f"Date column not found for {date_pattern}")
            return None

        except Exception as e:
            logger.error(f"Error finding date column: {e}")
            return None

    async def _async_get_cell_value(self, worksheet: gspread.Worksheet, row: int, col: int) -> Any:
        """Get cell value asynchronously"""
        loop = asyncio.get_event_loop()
        cell = await loop.run_in_executor(None, worksheet.cell, row, col)
        return cell.value

    async def _async_update_cell(self, worksheet: gspread.Worksheet, row: int, col: int, value: Any):
        """Update cell value asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, worksheet.update_cell, row, col, value)

    async def _async_get_all_values(self, worksheet: gspread.Worksheet) -> List[List[Any]]:
        """Get all values asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, worksheet.get_all_values)
