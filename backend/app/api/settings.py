"""
Settings API - Runtime configuration management
Handles Naver cookie updates, connection status checks, etc.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.real.reservation import RealReservationProvider
from app.auth.dependencies import get_current_user, require_admin_or_above
from app.api.deps import get_current_tenant, get_tenant_scoped_db
from app.db.models import User, Tenant
from app.services.activity_logger import log_activity
import hashlib
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Cookie audit + validation helpers ────────────────────────────
# 쿠키 저장은 민감하고 재발 이력(2026-07 'NAC'/'.' 오입력 사고)이 있는 변경이다.
# 근본원인은 엔드포인트가 '무검증·무감사'였다는 것 → 아래 두 축으로 보강한다:
#   1) _validate_naver_cookie: 길이/형식 검증으로 쓰레기값 저장 자체를 차단
#   2) _audit_cookie_change: 모든 입력(수락·거부)을 ActivityLog 로 기록
#      → 누가(created_by/actor) · 언제(created_at) · 어느 경로(route/ip/ua) 추적
MIN_NAVER_COOKIE_LEN = 50  # 정상 네이버 쿠키는 수백~1천여 자. 'NAC'(3)/'.'(1) 류 차단.


def _client_ip(request: Request) -> str:
    """X-Forwarded-For(프록시 뒤) 우선, 없으면 직접 접속 IP."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _cookie_fingerprint(cookie: str) -> dict:
    """전체 쿠키(민감정보)는 저장하지 않고 길이·마스킹 프리뷰·md5 앞자리만 남긴다.
    짧은 값(<=12)은 오입력 진단을 위해 원문 그대로 노출한다."""
    n = len(cookie)
    preview = cookie if n <= 12 else f"{cookie[:6]}…{cookie[-4:]}"
    return {
        "length": n,
        "preview": preview,
        "md5": hashlib.md5(cookie.encode("utf-8")).hexdigest()[:8],
    }


def _validate_naver_cookie(cookie: str) -> tuple[bool, str]:
    """네이버 쿠키 형식 검증 → (유효여부, 거부사유)."""
    if not cookie:
        return False, "empty"
    if len(cookie) < MIN_NAVER_COOKIE_LEN:
        return False, f"too_short(len={len(cookie)}<{MIN_NAVER_COOKIE_LEN})"
    if "=" not in cookie:
        return False, "no_kv_pair(missing '=')"
    return True, ""


def _audit_cookie_change(
    db: Session,
    request: Request,
    current_user: User,
    *,
    field: str,
    action: str,
    accepted: bool,
    reason: str,
    old_len: int,
    new_cookie: str | None,
) -> None:
    """쿠키 변경 시도(수락·거부 무관)를 ActivityLog 로 남기고 커밋한다.
    감사 로그 실패가 본 기능을 막지 않도록 예외를 삼킨다."""
    fp = _cookie_fingerprint(new_cookie) if new_cookie else {"length": 0, "preview": "", "md5": ""}
    verdict = "적용" if accepted else f"거부({reason})"
    detail = {
        "field": field,
        "action": action,
        "accepted": accepted,
        "reason": reason,
        "route": f"{request.method} {request.url.path}",
        "client_ip": _client_ip(request),
        "user_agent": request.headers.get("user-agent", ""),
        "actor": {
            "user_id": current_user.id,
            "username": current_user.username,
            "role": getattr(current_user.role, "value", str(current_user.role)),
        },
        "old_length": old_len,
        "new": fp,
    }
    try:
        log_activity(
            db,
            type="settings_cookie",
            title=f"네이버 쿠키 {action} : {current_user.username} → {verdict}",
            detail=detail,
            status="success" if accepted else "failed",
            target_count=1,
            success_count=1 if accepted else 0,
            failed_count=0 if accepted else 1,
            created_by=current_user.username,
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Cookie audit log failed: {e}")
        db.rollback()


class NaverCookieRequest(BaseModel):
    cookie: str


class NaverCookieStatus(BaseModel):
    has_cookie: bool
    cookie_length: int
    cookie_preview: str
    is_valid: bool | None = None
    source: str  # "runtime" or "env"
    business_id: str


@router.get("/naver/status", response_model=NaverCookieStatus)
async def get_naver_status(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Get current Naver cookie status and validate it"""
    # Use tenant's own settings only — no fallback to global config
    cookie = tenant.naver_cookie or ""
    business_id = tenant.naver_business_id or ""
    source = "tenant_db" if tenant.naver_cookie else "none"

    status = NaverCookieStatus(
        has_cookie=bool(cookie),
        cookie_length=len(cookie),
        cookie_preview=cookie[:10] + "***" + cookie[-5:] if len(cookie) > 20 else "***",
        is_valid=None,
        source=source,
        business_id=business_id,
    )

    # Test the cookie by making a lightweight API call
    if cookie:
        try:
            provider = RealReservationProvider(
                business_id=business_id,
                cookie=cookie,
            )
            reservations = await provider.sync_reservations()
            status.is_valid = True
            logger.info(f"Naver cookie validation: OK ({len(reservations)} reservations)")
        except Exception as e:
            status.is_valid = False
            logger.warning(f"Naver cookie validation failed: {e}")

    return status


@router.post("/naver/cookie")
async def update_naver_cookie(
    req: NaverCookieRequest,
    request: Request,
    current_user: User = Depends(require_admin_or_above),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_tenant_scoped_db),
):
    """Update Naver cookie — saves to Tenant table + runtime (검증 + 감사로그)"""
    old_len = len(tenant.naver_cookie or "")
    cleaned = re.sub(r'\s+', ' ', req.cookie).strip()

    # 1) 형식 검증 — 실패하면 저장하지 않고 거부 로그만 남긴다 ('NAC'/'.' 류 차단)
    ok, reason = _validate_naver_cookie(cleaned)
    if not ok:
        _audit_cookie_change(
            db, request, current_user,
            field="naver_cookie", action="update",
            accepted=False, reason=reason, old_len=old_len, new_cookie=cleaned,
        )
        logger.warning(f"Rejected invalid Naver cookie from {current_user.username}: {reason}")
        return {
            "success": False,
            "message": (
                f"쿠키 형식이 올바르지 않아 저장하지 않았습니다 (사유: {reason}, 길이 {len(cleaned)}자). "
                f"브라우저에서 전체 쿠키를 다시 복사해 주세요."
            ),
        }

    cookie = cleaned
    business_id = tenant.naver_business_id or ''

    # 2) Save to Tenant table (persistent across restarts)
    tenant.naver_cookie = cookie
    # tenant는 get_current_tenant(get_db 세션)에서 왔으므로 tenant 세션을 커밋
    from sqlalchemy import inspect as sa_inspect
    tenant_session = sa_inspect(tenant).session
    if tenant_session:
        tenant_session.commit()
    else:
        db.commit()

    # 3) 감사 로그 (수락) — 누가/언제/어느경로
    _audit_cookie_change(
        db, request, current_user,
        field="naver_cookie", action="update",
        accepted=True, reason="", old_len=old_len, new_cookie=cookie,
    )

    # 4) Validate the new cookie
    try:
        provider = RealReservationProvider(
            business_id=business_id,
            cookie=cookie,
        )
        reservations = await provider.sync_reservations()
        logger.info(f"New Naver cookie set and validated: {len(reservations)} reservations found")
        return {
            "success": True,
            "message": f"Cookie updated. {len(reservations)}건의 예약을 확인했습니다.",
            "reservation_count": len(reservations),
        }
    except Exception as e:
        logger.warning(f"New cookie set but validation failed: {e}")
        return {
            "success": True,
            "message": "Cookie saved but validation failed. Check if cookie is correct.",
            "warning": str(e),
        }


@router.delete("/naver/cookie")
async def clear_naver_cookie(
    request: Request,
    current_user: User = Depends(require_admin_or_above),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_tenant_scoped_db),
):
    """Clear Naver cookie from Tenant table + runtime (감사로그)"""
    old_len = len(tenant.naver_cookie or "")
    tenant.naver_cookie = None
    from sqlalchemy import inspect as sa_inspect
    tenant_session = sa_inspect(tenant).session
    if tenant_session:
        tenant_session.commit()
    else:
        db.commit()
    _audit_cookie_change(
        db, request, current_user,
        field="naver_cookie", action="clear",
        accepted=True, reason="", old_len=old_len, new_cookie=None,
    )
    return {"success": True, "message": "Cookie cleared."}


# ── Unstable Naver Settings ──────────────────────────────────────


class UnstableSettingsRequest(BaseModel):
    business_id: str | None = None
    cookie: str | None = None


@router.get("/unstable/status", response_model=NaverCookieStatus)
async def get_unstable_status(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Get unstable Naver cookie status and validate it"""
    cookie = tenant.unstable_cookie or ""
    business_id = tenant.unstable_business_id or ""
    source = "tenant_db" if tenant.unstable_cookie else "none"

    status = NaverCookieStatus(
        has_cookie=bool(cookie),
        cookie_length=len(cookie),
        cookie_preview=cookie[:10] + "***" + cookie[-5:] if len(cookie) > 20 else "***",
        is_valid=None,
        source=source,
        business_id=business_id,
    )

    if cookie and business_id:
        try:
            provider = RealReservationProvider(
                business_id=business_id,
                cookie=cookie,
            )
            reservations = await provider.sync_reservations()
            status.is_valid = True
            logger.info(f"Unstable cookie validation: OK ({len(reservations)} reservations)")
        except Exception as e:
            status.is_valid = False
            logger.warning(f"Unstable cookie validation failed: {e}")

    return status


@router.post("/unstable/settings")
async def update_unstable_settings(
    req: UnstableSettingsRequest,
    request: Request,
    current_user: User = Depends(require_admin_or_above),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_tenant_scoped_db),
):
    """Update unstable Naver business_id and/or cookie (쿠키 검증 + 감사로그)"""
    updated = []
    old_len = len(tenant.unstable_cookie or "")
    cookie_cleaned = None

    if req.business_id is not None:
        tenant.unstable_business_id = req.business_id.strip() or None
        updated.append("business_id")

    if req.cookie is not None:
        # 개행/탭/연속 공백 제거 (브라우저 복사 시 혼입되는 공백 정리)
        cookie_cleaned = re.sub(r'\s+', ' ', req.cookie).strip()
        # 비어있지 않은 값은 형식 검증 — 실패 시 저장하지 않고 거부 로그
        if cookie_cleaned:
            ok, reason = _validate_naver_cookie(cookie_cleaned)
            if not ok:
                _audit_cookie_change(
                    db, request, current_user,
                    field="unstable_cookie", action="update",
                    accepted=False, reason=reason, old_len=old_len, new_cookie=cookie_cleaned,
                )
                logger.warning(f"Rejected invalid unstable cookie from {current_user.username}: {reason}")
                return {
                    "success": False,
                    "message": f"언스테이블 쿠키 형식이 올바르지 않아 저장하지 않았습니다 (사유: {reason}).",
                }
        tenant.unstable_cookie = cookie_cleaned or None
        updated.append("cookie")

    if not updated:
        return {"success": False, "message": "변경할 항목이 없습니다."}

    # tenant는 get_current_tenant(get_db 세션)에서 왔으므로
    # tenant가 속한 세션을 직접 커밋해야 변경이 반영됨
    from sqlalchemy import inspect as sa_inspect
    tenant_session = sa_inspect(tenant).session
    if tenant_session:
        tenant_session.commit()
    else:
        db.commit()

    # 쿠키가 변경된 경우 감사 로그 (수락)
    if "cookie" in updated:
        _audit_cookie_change(
            db, request, current_user,
            field="unstable_cookie",
            action="update" if cookie_cleaned else "clear",
            accepted=True, reason="", old_len=old_len, new_cookie=cookie_cleaned or None,
        )

    # Validate if both business_id and cookie are present
    business_id = tenant.unstable_business_id or ""
    cookie = tenant.unstable_cookie or ""

    if cookie and business_id:
        try:
            provider = RealReservationProvider(
                business_id=business_id,
                cookie=cookie,
            )
            reservations = await provider.sync_reservations()
            logger.info(f"Unstable settings updated and validated: {len(reservations)} reservations")
            return {
                "success": True,
                "message": f"설정 저장 완료. {len(reservations)}건의 예약을 확인했습니다.",
                "reservation_count": len(reservations),
            }
        except Exception as e:
            logger.warning(f"Unstable settings saved but validation failed: {e}")
            return {
                "success": True,
                "message": "설정이 저장되었지만 연결 테스트에 실패했습니다.",
                "warning": str(e),
            }

    return {"success": True, "message": f"설정 저장 완료 ({', '.join(updated)})"}


@router.post("/unstable/sync")
async def sync_unstable_reservations(
    current_user: User = Depends(require_admin_or_above),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_tenant_scoped_db),
):
    """Manually trigger unstable Naver reservation sync"""
    if not tenant.unstable_business_id or not tenant.unstable_cookie:
        return {"success": False, "message": "언스테이블 Business ID와 쿠키를 먼저 설정해주세요."}

    from app.real.reservation import RealReservationProvider
    from app.services.naver_sync import sync_naver_to_db

    try:
        provider = RealReservationProvider(
            business_id=tenant.unstable_business_id,
            cookie=tenant.unstable_cookie,
        )
        result = await sync_naver_to_db(provider, db, source="unstable")
        return {
            "success": True,
            "message": result["message"],
            "added": result["added"],
            "updated": result["updated"],
        }
    except Exception as e:
        logger.error(f"Unstable manual sync failed: {e}")
        return {"success": False, "message": f"동기화 실패: {str(e)}"}


# ── Custom Highlight Colors ──────────────────────────────────────

class CustomHighlightColorsRequest(BaseModel):
    colors: list[str]  # list of hex color strings e.g. ["#FF5733"]


@router.get("/highlight-colors")
async def get_highlight_colors(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Get custom highlight colors for this tenant"""
    import json
    colors = []
    if tenant.custom_highlight_colors:
        try:
            colors = json.loads(tenant.custom_highlight_colors)
        except (json.JSONDecodeError, TypeError):
            colors = []
    return {"colors": colors}


@router.put("/highlight-colors")
async def update_highlight_colors(
    req: CustomHighlightColorsRequest,
    current_user: User = Depends(require_admin_or_above),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_tenant_scoped_db),
):
    """Update custom highlight colors for this tenant"""
    import json
    import re
    valid_colors = [c for c in req.colors if re.match(r'^#[0-9A-Fa-f]{6}$', c)]
    # tenant is from a different session (get_db), so merge into tenant-scoped session
    merged_tenant = db.merge(tenant)
    merged_tenant.custom_highlight_colors = json.dumps(valid_colors)
    db.commit()
    return {"success": True, "colors": valid_colors}



