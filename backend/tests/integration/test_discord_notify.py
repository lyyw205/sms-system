"""디스코드 알림 검증 — 핵심은 "알림이 본 작업을 절대 막지 않는다"."""
import pytest

from app.db.models import MessageTemplate
from app.services import discord_notify
from app.services.template_guard import log_template_activity


@pytest.fixture
def captured(monkeypatch):
    """스레드/네트워크 없이 payload 만 가로챈다."""
    sent = []

    def fake_thread(target, args, daemon=None):
        class _T:
            def start(self_inner):
                sent.append(args[1])   # payload
        return _T()

    monkeypatch.setattr(discord_notify.threading, "Thread",
                        lambda target, args, daemon=None: fake_thread(target, args, daemon))
    return sent


def _with_webhook(monkeypatch, url="https://discord.test/hook"):
    from app.config import settings
    monkeypatch.setattr(settings, "DISCORD_WEBHOOK_URL", url, raising=False)


class TestNoopWhenUnconfigured:
    def test_no_webhook_means_no_send(self, monkeypatch, captured):
        _with_webhook(monkeypatch, "")
        discord_notify.notify_template_change(
            action="deleted", kind="템플릿", name="x", created_by="u")
        assert captured == []


class TestPayload:
    def test_delete_includes_recovery_hint(self, monkeypatch, captured):
        _with_webhook(monkeypatch)
        discord_notify.notify_template_change(
            action="deleted", kind="템플릿", name="연박유도(여자)",
            created_by="apxogh", tenant_slug="stable")
        embed = captured[0]["embeds"][0]
        assert "삭제" in embed["title"]
        assert embed["color"] == 0xED4245  # 삭제는 빨강
        blob = str(embed["fields"])
        assert "연박유도(여자)" in blob and "apxogh" in blob and "stable" in blob
        assert "활동 로그" in blob  # 복구 안내

    def test_update_lists_changes(self, monkeypatch, captured):
        _with_webhook(monkeypatch)
        discord_notify.notify_template_change(
            action="updated", kind="템플릿", name="연박유도(남자)", created_by="u",
            changes={"male_buffer": {"before": 37, "after": 3}})
        blob = str(captured[0]["embeds"][0]["fields"])
        assert "male_buffer" in blob and "37" in blob and "3" in blob

    def test_long_values_are_trimmed(self, monkeypatch, captured):
        """디스코드 필드는 1024자 제한 — 초과하면 웹훅이 400 을 낸다."""
        _with_webhook(monkeypatch)
        discord_notify.notify_template_change(
            action="updated", kind="템플릿", name="x", created_by="u",
            changes={f"f{i}": {"before": "가" * 500, "after": "나" * 500} for i in range(20)})
        for f in captured[0]["embeds"][0]["fields"]:
            assert len(f["value"]) <= 1024

    def test_newlines_do_not_break_embed(self, monkeypatch, captured):
        _with_webhook(monkeypatch)
        discord_notify.notify_template_change(
            action="updated", kind="템플릿", name="x", created_by="u",
            changes={"content": {"before": "a\nb\nc", "after": "d\ne"}})
        blob = str(captured[0]["embeds"][0]["fields"])
        assert "⏎" in blob


class TestNeverBreaksCaller:
    """알림 실패가 템플릿 저장/삭제를 되돌리면 안 된다."""

    def test_send_failure_is_swallowed(self, monkeypatch):
        _with_webhook(monkeypatch)

        def boom(*a, **k):
            raise RuntimeError("discord down")

        monkeypatch.setattr(discord_notify.threading, "Thread", boom)
        discord_notify.notify_template_change(
            action="deleted", kind="템플릿", name="x", created_by="u")

    def test_audit_still_written_when_notify_fails(self, db, monkeypatch):
        from app.db.models import ActivityLog

        def boom(*a, **k):
            raise RuntimeError("discord down")

        monkeypatch.setattr(discord_notify, "notify_template_change", boom)
        t = MessageTemplate(template_key="k", name="n", content="c")
        db.add(t)
        db.flush()

        log_template_activity(db, action="deleted", kind="템플릿", name="n",
                              created_by="u", snapshot={"content": "c"})
        assert db.query(ActivityLog).filter(
            ActivityLog.activity_type == "template_deleted").count() == 1
