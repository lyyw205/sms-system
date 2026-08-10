"""디스코드 웹훅 알림 — 템플릿/스케줄 변경 실시간 통지.

배경: 2026-06 / 2026-08-04 두 차례 운영 중인 템플릿이 삭제됐는데 아무도
즉시 알아채지 못했다. 6월 건은 발견까지 7주가 걸렸고 그 사이 diag 로그
보존기간(7일)이 지나 추적 자체가 불가능해졌다. ActivityLog 승격으로 "나중에
찾을 수는" 있게 됐지만, **그 순간 알아채는** 수단이 따로 필요하다.

설계 원칙 (전부 호출자 보호용):
1. 웹훅 미설정(`DISCORD_WEBHOOK_URL` 빈 값)이면 즉시 no-op — 로컬/테스트 무영향
2. 별도 스레드로 발송 — 디스코드가 느리거나 죽어도 API 응답을 막지 않음
3. 어떤 예외도 삼킴 — 알림 실패가 템플릿 저장/삭제를 되돌리면 안 됨
4. 본문은 요약만 — 전문 복구는 ActivityLog 스냅샷 담당
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 5

# 동작별 색상/이모지 — 삭제가 한눈에 띄어야 한다
_STYLE = {
    "created": ("🆕", 0x3BA55D),   # green
    "updated": ("✏️", 0x5865F2),   # blurple
    "deleted": ("🗑️", 0xED4245),   # red
    "locked":  ("🔒", 0x949BA4),   # grey
}


def _post(url: str, payload: dict) -> None:
    try:
        import httpx

        with httpx.Client(timeout=_TIMEOUT_SEC) as client:
            resp = client.post(url, json=payload)
            if resp.status_code >= 400:
                logger.warning(
                    "discord_notify: webhook %s -> %s", resp.status_code, resp.text[:200]
                )
    except Exception as e:  # pragma: no cover — 알림 실패는 본 작업과 무관
        logger.warning("discord_notify: send failed (%s)", e)


def _fmt_changes(changes: dict) -> str:
    """{'name': {'before': a, 'after': b}} → 사람이 읽는 줄 목록."""
    lines = []
    for field, ba in list(changes.items())[:8]:
        if isinstance(ba, dict) and "before" in ba and "after" in ba:
            before, after = _trim(ba["before"]), _trim(ba["after"])
            lines.append(f"• **{field}**: `{before}` → `{after}`")
        else:
            lines.append(f"• **{field}**: `{_trim(ba)}`")
    if len(changes) > 8:
        lines.append(f"… 외 {len(changes) - 8}건")
    return "\n".join(lines) if lines else "(변경 내용 없음)"


def _trim(v: Any, limit: int = 60) -> str:
    s = "(없음)" if v is None else str(v)
    s = s.replace("\n", "⏎")
    return s if len(s) <= limit else s[:limit] + "…"


def notify_template_change(
    *,
    action: str,
    kind: str,
    name: str,
    created_by: str,
    tenant_slug: Optional[str] = None,
    changes: Optional[dict] = None,
    extra: Optional[str] = None,
) -> None:
    """템플릿/스케줄 변경을 디스코드로 통지 (fire-and-forget).

    Args:
        action: 'created' | 'updated' | 'deleted' | 'locked'
        kind:   '템플릿' | '스케줄'
        name:   대상 이름
        created_by: 수정한 사용자명
    """
    try:
        from app.config import settings

        url = getattr(settings, "DISCORD_WEBHOOK_URL", "") or ""
        if not url:
            return  # 미설정 — 조용히 통과

        emoji, color = _STYLE.get(action, ("📝", 0x5865F2))
        labels = {"created": "생성", "updated": "수정", "deleted": "삭제", "locked": "잠금"}
        label = labels.get(action, action)

        fields = [
            {"name": "대상", "value": f"{kind} · **{name}**", "inline": True},
            {"name": "수정자", "value": created_by or "(알 수 없음)", "inline": True},
        ]
        if tenant_slug:
            fields.append({"name": "테넌트", "value": tenant_slug, "inline": True})
        if changes:
            fields.append({"name": "변경 내용", "value": _fmt_changes(changes)[:1024], "inline": False})
        if extra:
            fields.append({"name": "비고", "value": extra[:1024], "inline": False})
        if action == "deleted":
            fields.append({
                "name": "복구",
                "value": "활동 로그에 본문·설정 전문이 스냅샷으로 남아 있습니다.",
                "inline": False,
            })

        payload = {
            "embeds": [{
                "title": f"{emoji} {kind} {label}",
                "color": color,
                "fields": fields,
            }]
        }

        threading.Thread(target=_post, args=(url, payload), daemon=True).start()
    except Exception as e:  # pragma: no cover
        logger.warning("discord_notify: skipped (%s)", e)
