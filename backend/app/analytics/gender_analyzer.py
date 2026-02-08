"""
Gender Analyzer - Extract and analyze gender statistics for party planning
Ported from stable-clasp-main/function_extractGenderCount.js
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import re
import logging

from ..db.models import GenderStat
from ..providers.base import StorageProvider

logger = logging.getLogger(__name__)


class GenderAnalyzer:
    """
    Analyzer for gender statistics from Google Sheets

    Ported from: stable-clasp-main/function_extractGenderCount.js
    """

    def __init__(self, db: Session, storage_provider: Optional[StorageProvider] = None):
        self.db = db
        self.storage_provider = storage_provider

    async def extract_gender_stats(self, date: datetime) -> Optional[GenderStat]:
        """
        Extract gender statistics from Google Sheets

        Args:
            date: Date to extract stats for

        Returns:
            GenderStat record or None if extraction fails

        Ported from: stable-clasp-main/function_extractGenderCount.js
        """
        if not self.storage_provider:
            logger.error("Storage provider not available for gender stats extraction")
            return None

        try:
            # Get sheet name (YYYYMM format)
            sheet_name = date.strftime("%Y%m")

            # Get cell value from row 134, column offset +5
            # This cell contains gender stats in format "남: X / 여: Y"
            cell_value = await self.storage_provider.get_cell_value(
                sheet_name,
                134,
                5  # Column offset
            )

            if not cell_value:
                logger.warning(f"No gender stats found for {date}")
                return None

            # Parse using regex (from line 7-8)
            # Pattern: "남: X / 여: Y" or "남:X/여:Y"
            regex = r"남:\s*(\d+)\s*/\s*여:\s*(\d+)"
            match = re.match(regex, str(cell_value))

            if not match:
                logger.warning(f"Gender stats format invalid: {cell_value}")
                return None

            # Extract counts (from line 10-16)
            male_count = int(match.group(1))
            female_count = int(match.group(2))
            total = male_count + female_count

            logger.info(f"Extracted gender stats for {date}: M={male_count}, F={female_count}")

            # Create or update GenderStat record
            date_str = date.strftime("%Y-%m-%d")

            stat = self.db.query(GenderStat).filter_by(date=date_str).first()

            if stat:
                # Update existing
                stat.male_count = male_count
                stat.female_count = female_count
                stat.total_participants = total
                stat.updated_at = datetime.utcnow()
            else:
                # Create new
                stat = GenderStat(
                    date=date_str,
                    male_count=male_count,
                    female_count=female_count,
                    total_participants=total
                )
                self.db.add(stat)

            self.db.commit()
            self.db.refresh(stat)

            return stat

        except Exception as e:
            logger.error(f"Error extracting gender stats: {e}")
            return None

    def get_gender_stats(self, date: datetime) -> Optional[GenderStat]:
        """Get gender statistics from database"""
        date_str = date.strftime("%Y-%m-%d")
        return self.db.query(GenderStat).filter_by(date=date_str).first()

    def generate_invite_message(self, stat: GenderStat) -> str:
        """
        Generate dynamic invite message based on gender ratio

        Args:
            stat: GenderStat record

        Returns:
            Formatted invite message

        Ported from: stable-clasp-main/01_sns.js:260-270 (inviteGirlMessage logic)
        """
        male = stat.male_count
        female = stat.female_count
        total = stat.total_participants

        # Calculate ratio
        if total == 0:
            ratio_str = "아직 참여자가 없습니다"
        else:
            male_pct = round((male / total) * 100)
            female_pct = round((female / total) * 100)
            ratio_str = f"남자 {male_pct}% / 여자 {female_pct}%"

        message = f"""
현재 파티 참여 현황입니다!

총 인원: {total}명
남자: {male}명
여자: {female}명
비율: {ratio_str}

여성 분들의 많은 참여 부탁드립니다! 🎉

파티 시간: 저녁 8시
장소: 스테이블 B동 1층 포차
        """.strip()

        return message

    def calculate_party_balance(self, stat: GenderStat) -> Dict[str, Any]:
        """
        Calculate party gender balance metrics

        Returns:
            Dictionary with balance analysis
        """
        male = stat.male_count
        female = stat.female_count
        total = stat.total_participants

        if total == 0:
            return {
                'balance': 'no_data',
                'recommendation': 'Need participants',
                'male_pct': 0,
                'female_pct': 0
            }

        male_pct = (male / total) * 100
        female_pct = (female / total) * 100

        # Determine balance
        if abs(male_pct - female_pct) < 10:
            balance = 'balanced'
            recommendation = 'Good balance!'
        elif male_pct > female_pct:
            balance = 'male_heavy'
            recommendation = f'Need {int((male - female) / 2)} more women for balance'
        else:
            balance = 'female_heavy'
            recommendation = f'Need {int((female - male) / 2)} more men for balance'

        return {
            'balance': balance,
            'recommendation': recommendation,
            'male_pct': round(male_pct, 1),
            'female_pct': round(female_pct, 1),
            'male_count': male,
            'female_count': female,
            'total': total
        }
