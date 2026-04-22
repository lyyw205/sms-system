"""_resolve_date_target() 유닛 테스트 — static method, DB 불필요."""
from datetime import timedelta
from unittest.mock import patch
from app.scheduler.template_scheduler import TemplateScheduleExecutor
from app.config import today_kst, today_kst_date


class TestResolveDateTarget:
    def test_today(self):
        result = TemplateScheduleExecutor._resolve_date_target('today')
        assert result == today_kst()

    def test_tomorrow(self):
        result = TemplateScheduleExecutor._resolve_date_target('tomorrow')
        expected = (today_kst_date() + timedelta(days=1)).strftime('%Y-%m-%d')
        assert result == expected

    def test_yesterday(self):
        result = TemplateScheduleExecutor._resolve_date_target('yesterday')
        expected = (today_kst_date() - timedelta(days=1)).strftime('%Y-%m-%d')
        assert result == expected

    def test_unknown_falls_back_to_today(self):
        """알 수 없는 값(레거시 포함)은 today로 fallback."""
        result = TemplateScheduleExecutor._resolve_date_target('today_checkout')
        assert result == today_kst()
