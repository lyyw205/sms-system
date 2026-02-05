"""
Mock Storage Provider for demo mode.
Uses CSV files instead of actual Google Sheets.
"""
import csv
from typing import List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MockStorageProvider:
    """Mock storage provider - uses CSV files instead of Google Sheets"""

    def __init__(self):
        self.data_dir = Path("app/mock/data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def sync_to_storage(self, data: List[Dict[str, Any]], sheet_name: str) -> bool:
        """Export data to CSV file (simulating Google Sheets export)"""
        csv_file = self.data_dir / f"{sheet_name}.csv"

        logger.info(
            f"📊 [MOCK GOOGLE SHEETS SYNC]\n"
            f"   Writing to: {csv_file}\n"
            f"   Records: {len(data)}\n"
            f"   ⚠️  In production mode, this will sync to actual Google Sheets"
        )

        try:
            if not data:
                logger.warning("   No data to export")
                return False

            # Get all keys from all dictionaries
            all_keys = set()
            for record in data:
                all_keys.update(record.keys())
            fieldnames = sorted(list(all_keys))

            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            logger.info(f"   ✅ Successfully exported to {csv_file}")
            return True
        except Exception as e:
            logger.error(f"   ❌ Export failed: {e}")
            return False

    async def sync_from_storage(self, sheet_name: str) -> List[Dict[str, Any]]:
        """Import data from CSV file (simulating Google Sheets import)"""
        csv_file = self.data_dir / f"{sheet_name}.csv"

        logger.info(
            f"📊 [MOCK GOOGLE SHEETS IMPORT]\n"
            f"   Reading from: {csv_file}\n"
            f"   ⚠️  In production mode, this will read from actual Google Sheets"
        )

        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                data = list(reader)
                logger.info(f"   ✅ Read {len(data)} records")
                return data
        except FileNotFoundError:
            logger.warning(f"   File not found: {csv_file}")
            return []
        except Exception as e:
            logger.error(f"   ❌ Import failed: {e}")
            return []
