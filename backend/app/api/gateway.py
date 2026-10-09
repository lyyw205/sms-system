"""
SMS Gateway API — 안드로이드 게이트웨이 폰 ↔ 서버 연동.

## 왜 폴링인가
폰은 LTE NAT 뒤에 있어 서버가 폰을 직접 호출할 수 없다. 그래서 방향을 뒤집어
**폰이 서버에게 물어보는** 단방향 구조로 만든다. 덕분에 고정 IP / VPN / 클라우드
릴레이가 전부 불필요하고, 문자 내용이 지나가는 경로가 [폰 → 우리 서버] 하나로 고정된다.

## 엔드포인트 두 갈래
- 기기용 (`X-Device-Token` 인증): enroll / status / inbound / sent / outbox / result / heartbeat
- 운영자용 (JWT 인증): devices 목록·승인·폐기, threads, reply

## 페어링 (사용자가 파라미터를 직접 입력하지 않게)
앱 설치 → 권한 허용 → 앱이 스스로 enroll → 화면에 pairing_code 표시
→ 운영자에게 코드만 알려줌 → 관리 화면에서 승인 → 끝.

주의: enroll 은 인증 없이 열려 있다. 대신 (a) 발급 즉시는 is_active=False 라
아무 것도 못 하고, (b) 테넌트별 미승인 기기 수에 상한을 둔다.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_scoped_db
from app.auth.dependencies import get_current_user, require_role
from app.db.database import session_bypass, session_for_tenant
from app.db.models import (
    Reservation,
    ReservationStatus,
    SmsAttachment,
    SmsDevice,
    SmsMessage,
    Tenant,
    User,
    UserRole,
)
from app.diag_logger import diag, mask_phone

router = APIRouter(prefix="/api/gateway", tags=["gateway"])

require_admin_or_above = require_role(UserRole.SUPERADMIN, UserRole.ADMIN)

# 미승인 기기가 무한정 쌓이지 않도록 하는 상한 (enroll 남용 방지)
MAX_PENDING_DEVICES = 5
# 폰이 한 번에 가져갈 발송 건수
OUTBOX_BATCH = 10
# 가져간 뒤 이 시간 안에 결과 보고가 없으면 재배포 (앱이 죽은 경우 복구)
CLAIM_TIMEOUT = timedelta(minutes=5)
# MMS 첨부 1건 최대 크기 — DB 직접 보관이므로 보수적으로 잡는다
MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_phone(raw: Optional[str]) -> str:
    """전화번호를 숫자만 남긴 형태로 정규화.

    reservations.phone 이 '01055973129' 형태로 저장돼 있어 그 형식에 맞춘다.
    +8210... 로 들어오는 경우 국내 0 접두 형태로 되돌린다.
    """
    if not raw:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("82") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits


def _gen_token() -> str:
    return secrets.token_urlsafe(32)[:48]


def _gen_pairing_code() -> str:
    """사람이 전화로 불러줄 수 있는 코드. 헷갈리는 글자(0/O, 1/I) 제외."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)]
    return "-".join(groups)


def _match_reservation(db: Session, phone: str) -> Optional[int]:
    """수신 번호로 예약을 best-effort 매칭.

    같은 번호의 예약이 여러 건이면 체크인이 오늘에 가장 가까운 CONFIRMED 건을 고른다.
    못 찾아도 문자 적재 자체는 진행한다(매칭은 부가 정보).
    """
    if not phone:
        return None
    try:
        row = (
            db.query(Reservation.id)
            .filter(
                Reservation.phone == phone,
                Reservation.status == ReservationStatus.CONFIRMED,
            )
            .order_by(Reservation.check_in_date.desc())
            .first()
        )
        return row[0] if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 기기 인증
# ---------------------------------------------------------------------------

class DeviceCtx:
    def __init__(self, db: Session, device: SmsDevice):
        self.db = db
        self.device = device


async def device_ctx(
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
):
    """X-Device-Token → 테넌트 스코프 세션 + SmsDevice.

    토큰 조회 시점엔 테넌트를 모르므로 bypass 세션으로 한 번만 찾고,
    이후 작업은 그 기기의 테넌트로 격리된 세션에서 수행한다.
    """
    if not x_device_token:
        raise HTTPException(status_code=401, detail="기기 토큰이 필요합니다")

    lookup = session_bypass()
    try:
        row = lookup.query(SmsDevice).filter(SmsDevice.token == x_device_token).first()
        if row is None:
            raise HTTPException(status_code=401, detail="등록되지 않은 기기입니다")
        tenant_id, device_id = row.tenant_id, row.id
    finally:
        lookup.close()

    db = session_for_tenant(tenant_id)
    try:
        device = db.query(SmsDevice).filter(SmsDevice.id == device_id).first()
        if device is None:
            raise HTTPException(status_code=401, detail="등록되지 않은 기기입니다")
        device.last_seen_at = utcnow()
        db.commit()
        yield DeviceCtx(db=db, device=device)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def active_device_ctx(ctx: DeviceCtx = Depends(device_ctx)) -> DeviceCtx:
    if not ctx.device.is_active:
        raise HTTPException(status_code=403, detail="승인 대기 중인 기기입니다")
    return ctx


# ---------------------------------------------------------------------------
# 1) 페어링
# ---------------------------------------------------------------------------

class EnrollRequest(BaseModel):
    tenant_slug: str                      # APK 에 박아둠 — 사용자가 입력하지 않는다
    device_uid: str = Field(min_length=8, max_length=64)
    model: Optional[str] = None
    app_version: Optional[str] = None
    phone_number: Optional[str] = None


class EnrollResponse(BaseModel):
    token: str
    pairing_code: str
    is_active: bool


@router.post("/enroll", response_model=EnrollResponse)
async def enroll_device(request: EnrollRequest):
    """앱 최초 실행 시 1회 호출. 승인 전까지는 아무 것도 못 하는 토큰을 발급한다."""
    lookup = session_bypass()
    try:
        tenant = (
            lookup.query(Tenant)
            .filter(Tenant.slug == request.tenant_slug, Tenant.is_active == True)  # noqa: E712
            .first()
        )
        if tenant is None:
            raise HTTPException(status_code=404, detail="유효하지 않은 테넌트입니다")
        tenant_id = tenant.id
    finally:
        lookup.close()

    db = session_for_tenant(tenant_id)
    try:
        existing = (
            db.query(SmsDevice)
            .filter(SmsDevice.device_uid == request.device_uid)
            .first()
        )
        if existing:
            # 앱 재설치가 아닌 단순 재시도 — 같은 토큰을 그대로 돌려준다(멱등).
            existing.model = request.model or existing.model
            existing.app_version = request.app_version or existing.app_version
            if request.phone_number:
                existing.phone_number = normalize_phone(request.phone_number)
            db.commit()
            return EnrollResponse(
                token=existing.token,
                pairing_code=existing.pairing_code,
                is_active=existing.is_active,
            )

        pending = (
            db.query(func.count(SmsDevice.id))
            .filter(SmsDevice.is_active == False)  # noqa: E712
            .scalar()
        ) or 0
        if pending >= MAX_PENDING_DEVICES:
            raise HTTPException(
                status_code=429,
                detail="승인 대기 기기가 너무 많습니다. 관리자에게 문의하세요.",
            )

        device = SmsDevice(
            device_uid=request.device_uid,
            token=_gen_token(),
            pairing_code=_gen_pairing_code(),
            model=request.model,
            app_version=request.app_version,
            phone_number=normalize_phone(request.phone_number),
            is_active=False,
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        diag(
            "gateway.device.enrolled",
            level="critical",
            tid=tenant_id,
            device_id=device.id,
            model=request.model,
        )
        return EnrollResponse(
            token=device.token,
            pairing_code=device.pairing_code,
            is_active=False,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class DeviceStatusResponse(BaseModel):
    is_active: bool
    pairing_code: str
    tenant_name: Optional[str] = None
    poll_interval_sec: int = 10
    daily_send_limit: int = 200
    min_send_gap_sec: int = 3


@router.get("/status", response_model=DeviceStatusResponse)
async def device_status(ctx: DeviceCtx = Depends(device_ctx)):
    """앱이 주기적으로 호출 — 승인 여부와 동작 파라미터를 서버가 내려준다.

    앱에 설정 화면을 만들지 않기 위해, 폴링 주기·발송 상한 같은 값도 전부 여기서 준다.
    """
    tenant = ctx.db.query(Tenant).filter(Tenant.id == ctx.device.tenant_id).first()
    return DeviceStatusResponse(
        is_active=ctx.device.is_active,
        pairing_code=ctx.device.pairing_code,
        tenant_name=tenant.name if tenant else None,
    )


class HeartbeatRequest(BaseModel):
    battery_level: Optional[int] = None
    app_version: Optional[str] = None
    phone_number: Optional[str] = None


@router.post("/heartbeat")
async def heartbeat(request: HeartbeatRequest, ctx: DeviceCtx = Depends(device_ctx)):
    d = ctx.device
    if request.battery_level is not None:
        d.battery_level = request.battery_level
    if request.app_version:
        d.app_version = request.app_version
    if request.phone_number:
        d.phone_number = normalize_phone(request.phone_number)
    ctx.db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# 2) 수신 적재
# ---------------------------------------------------------------------------

class InboundItem(BaseModel):
    client_msg_id: str = Field(min_length=8, max_length=64)
    peer_phone: str
    body: Optional[str] = None
    occurred_at: Optional[datetime] = None
    is_mms: bool = False
    provider_id: Optional[str] = None


class InboundRequest(BaseModel):
    messages: List[InboundItem]


class InboundAccepted(BaseModel):
    client_msg_id: str
    message_id: int
    duplicate: bool


@router.post("/inbound", response_model=List[InboundAccepted])
async def report_inbound(
    request: InboundRequest,
    ctx: DeviceCtx = Depends(active_device_ctx),
):
    """폰이 받은 문자를 적재. 앱 재시도를 대비해 client_msg_id 로 멱등 처리."""
    db = ctx.db
    out: List[InboundAccepted] = []

    for item in request.messages:
        dup = (
            db.query(SmsMessage)
            .filter(SmsMessage.client_msg_id == item.client_msg_id)
            .first()
        )
        if dup:
            out.append(
                InboundAccepted(
                    client_msg_id=item.client_msg_id, message_id=dup.id, duplicate=True
                )
            )
            continue

        phone = normalize_phone(item.peer_phone)
        msg = SmsMessage(
            direction="in",
            peer_phone=phone,
            body=item.body,
            status="received",
            source="gateway",
            device_id=ctx.device.id,
            client_msg_id=item.client_msg_id,
            provider_id=item.provider_id,
            is_mms=item.is_mms,
            reservation_id=_match_reservation(db, phone),
            occurred_at=item.occurred_at.replace(tzinfo=None)
            if item.occurred_at
            else utcnow(),
        )
        db.add(msg)
        db.flush()
        out.append(
            InboundAccepted(
                client_msg_id=item.client_msg_id, message_id=msg.id, duplicate=False
            )
        )

        diag(
            "gateway.inbound.received",
            level="critical",
            tid=ctx.device.tenant_id,
            message_id=msg.id,
            phone=mask_phone(phone),
            is_mms=item.is_mms,
            matched_reservation=msg.reservation_id,
        )

    db.commit()
    return out


@router.post("/attachment")
async def upload_attachment(
    message_id: int = Form(...),
    file: UploadFile = File(...),
    ctx: DeviceCtx = Depends(active_device_ctx),
):
    """MMS 첨부 업로드. inbound 로 메시지를 먼저 만든 뒤 그 id 로 올린다."""
    db = ctx.db
    msg = db.query(SmsMessage).filter(SmsMessage.id == message_id).first()
    if msg is None:
        raise HTTPException(status_code=404, detail="메시지를 찾을 수 없습니다")

    data = await file.read()
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"첨부가 너무 큽니다 ({len(data)} bytes > {MAX_ATTACHMENT_BYTES})",
        )

    att = SmsAttachment(
        message_id=msg.id,
        content_type=file.content_type,
        filename=file.filename,
        size_bytes=len(data),
        data=data,
    )
    db.add(att)
    msg.is_mms = True
    db.commit()
    db.refresh(att)

    diag(
        "gateway.attachment.stored",
        level="critical",
        tid=ctx.device.tenant_id,
        message_id=msg.id,
        attachment_id=att.id,
        size=len(data),
        content_type=file.content_type,
    )
    return {"attachment_id": att.id, "size_bytes": att.size_bytes}


class SentItem(BaseModel):
    """폰 기본 문자앱에서 직원이 직접 보낸 발신분 (ContentObserver 캡처)."""
    provider_id: str = Field(min_length=1, max_length=32)
    peer_phone: str
    body: Optional[str] = None
    occurred_at: Optional[datetime] = None
    is_mms: bool = False


class SentRequest(BaseModel):
    messages: List[SentItem]


@router.post("/sent")
async def report_phone_sent(
    request: SentRequest,
    ctx: DeviceCtx = Depends(active_device_ctx),
):
    """폰에서 직접 보낸 문자 캡처.

    content://sms 는 전송중(type=4) → 전송완료(type=2) 로 두 번 감지되므로
    provider_id 로 중복을 막는다.
    """
    db = ctx.db
    created = 0
    for item in request.messages:
        dup = (
            db.query(SmsMessage)
            .filter(
                SmsMessage.direction == "out",
                SmsMessage.provider_id == item.provider_id,
            )
            .first()
        )
        if dup:
            continue

        phone = normalize_phone(item.peer_phone)
        db.add(
            SmsMessage(
                direction="out",
                peer_phone=phone,
                body=item.body,
                status="sent",
                source="phone",
                device_id=ctx.device.id,
                provider_id=item.provider_id,
                is_mms=item.is_mms,
                reservation_id=_match_reservation(db, phone),
                occurred_at=item.occurred_at.replace(tzinfo=None)
                if item.occurred_at
                else utcnow(),
            )
        )
        created += 1

    db.commit()
    if created:
        diag(
            "gateway.phone_sent.captured",
            level="critical",
            tid=ctx.device.tenant_id,
            count=created,
        )
    return {"created": created}


# ---------------------------------------------------------------------------
# 3) 발송 큐
# ---------------------------------------------------------------------------

class OutboxItem(BaseModel):
    id: int
    to: str
    text: str


@router.get("/outbox", response_model=List[OutboxItem])
async def claim_outbox(ctx: DeviceCtx = Depends(active_device_ctx)):
    """보낼 문자를 가져간다(claim). 결과 보고가 없으면 CLAIM_TIMEOUT 후 재배포."""
    db = ctx.db
    now = utcnow()

    # 죽은 claim 회수
    stale = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.direction == "out",
            SmsMessage.status == "sending",
            SmsMessage.claimed_at < now - CLAIM_TIMEOUT,
        )
        .all()
    )
    for m in stale:
        m.status = "pending"
        m.claimed_at = None

    rows = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.direction == "out",
            SmsMessage.status == "pending",
        )
        .order_by(SmsMessage.created_at.asc())
        .limit(OUTBOX_BATCH)
        .all()
    )

    items: List[OutboxItem] = []
    for m in rows:
        m.status = "sending"
        m.claimed_at = now
        m.device_id = ctx.device.id
        m.attempts = (m.attempts or 0) + 1
        items.append(OutboxItem(id=m.id, to=m.peer_phone, text=m.body or ""))

    db.commit()
    return items


class SendResult(BaseModel):
    id: int
    success: bool
    error: Optional[str] = None
    provider_id: Optional[str] = None
    occurred_at: Optional[datetime] = None


class ResultRequest(BaseModel):
    results: List[SendResult]


@router.post("/result")
async def report_send_result(
    request: ResultRequest,
    ctx: DeviceCtx = Depends(active_device_ctx),
):
    db = ctx.db
    for r in request.results:
        m = db.query(SmsMessage).filter(SmsMessage.id == r.id).first()
        if m is None or m.direction != "out":
            continue
        m.status = "sent" if r.success else "failed"
        m.error = None if r.success else (r.error or "unknown")
        m.source = "gateway"
        if r.provider_id:
            m.provider_id = r.provider_id
        m.occurred_at = (
            r.occurred_at.replace(tzinfo=None) if r.occurred_at else utcnow()
        )
        diag(
            "gateway.send.result",
            level="critical",
            tid=ctx.device.tenant_id,
            message_id=m.id,
            success=r.success,
            error=m.error,
        )
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# 4) 운영자용 (JWT)
# ---------------------------------------------------------------------------

class DeviceOut(BaseModel):
    id: int
    pairing_code: str
    label: Optional[str]
    phone_number: Optional[str]
    model: Optional[str]
    app_version: Optional[str]
    is_active: bool
    last_seen_at: Optional[datetime]
    battery_level: Optional[int]
    created_at: Optional[datetime]


@router.get(
    "/devices",
    response_model=List[DeviceOut],
    dependencies=[Depends(require_admin_or_above)],
)
async def list_devices(db: Session = Depends(get_tenant_scoped_db)):
    rows = db.query(SmsDevice).order_by(SmsDevice.created_at.desc()).all()
    return [
        DeviceOut(
            id=d.id,
            pairing_code=d.pairing_code,
            label=d.label,
            phone_number=d.phone_number,
            model=d.model,
            app_version=d.app_version,
            is_active=d.is_active,
            last_seen_at=d.last_seen_at,
            battery_level=d.battery_level,
            created_at=d.created_at,
        )
        for d in rows
    ]


class ApproveRequest(BaseModel):
    pairing_code: str
    label: Optional[str] = None


@router.post(
    "/devices/approve",
    response_model=DeviceOut,
    dependencies=[Depends(require_admin_or_above)],
)
async def approve_device(
    request: ApproveRequest,
    db: Session = Depends(get_tenant_scoped_db),
    current_user: User = Depends(get_current_user),
):
    """앱 화면에 뜬 코드를 입력해 기기를 승인한다."""
    code = request.pairing_code.strip().upper()
    device = db.query(SmsDevice).filter(SmsDevice.pairing_code == code).first()
    if device is None:
        raise HTTPException(status_code=404, detail="해당 코드의 기기를 찾을 수 없습니다")

    device.is_active = True
    device.approved_at = utcnow()
    device.approved_by = current_user.username
    if request.label:
        device.label = request.label
    db.commit()
    db.refresh(device)

    diag(
        "gateway.device.approved",
        level="critical",
        tid=device.tenant_id,
        device_id=device.id,
        actor=current_user.username,
    )
    return DeviceOut(
        id=device.id,
        pairing_code=device.pairing_code,
        label=device.label,
        phone_number=device.phone_number,
        model=device.model,
        app_version=device.app_version,
        is_active=device.is_active,
        last_seen_at=device.last_seen_at,
        battery_level=device.battery_level,
        created_at=device.created_at,
    )


@router.delete(
    "/devices/{device_id}",
    dependencies=[Depends(require_admin_or_above)],
)
async def revoke_device(
    device_id: int,
    db: Session = Depends(get_tenant_scoped_db),
    current_user: User = Depends(get_current_user),
):
    """기기 폐기 — 토큰을 즉시 무효화한다(분실/교체 대응)."""
    device = db.query(SmsDevice).filter(SmsDevice.id == device_id).first()
    if device is None:
        raise HTTPException(status_code=404, detail="기기를 찾을 수 없습니다")
    device.is_active = False
    device.token = _gen_token()  # 기존 토큰 무효화
    db.commit()
    diag(
        "gateway.device.revoked",
        level="critical",
        device_id=device_id,
        actor=current_user.username,
    )
    return {"ok": True}


class MessageOut(BaseModel):
    id: int
    direction: str
    peer_phone: str
    body: Optional[str]
    status: str
    source: str
    is_mms: bool
    reservation_id: Optional[int]
    customer_name: Optional[str] = None
    attachment_ids: List[int] = []
    occurred_at: Optional[datetime]
    created_at: Optional[datetime]


@router.get(
    "/messages",
    response_model=List[MessageOut],
    dependencies=[Depends(require_admin_or_above)],
)
async def list_messages(
    peer_phone: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_tenant_scoped_db),
):
    """대화 목록. peer_phone 을 주면 그 번호와의 스레드만."""
    q = db.query(SmsMessage)
    if peer_phone:
        q = q.filter(SmsMessage.peer_phone == normalize_phone(peer_phone))
    rows = q.order_by(SmsMessage.occurred_at.desc()).limit(min(limit, 500)).all()

    res_ids = {m.reservation_id for m in rows if m.reservation_id}
    names = {}
    if res_ids:
        for rid, name in db.query(Reservation.id, Reservation.customer_name).filter(
            Reservation.id.in_(res_ids)
        ):
            names[rid] = name

    msg_ids = [m.id for m in rows]
    att_map: dict[int, List[int]] = {}
    if msg_ids:
        for aid, mid in db.query(SmsAttachment.id, SmsAttachment.message_id).filter(
            SmsAttachment.message_id.in_(msg_ids)
        ):
            att_map.setdefault(mid, []).append(aid)

    return [
        MessageOut(
            id=m.id,
            direction=m.direction,
            peer_phone=m.peer_phone,
            body=m.body,
            status=m.status,
            source=m.source,
            is_mms=m.is_mms,
            reservation_id=m.reservation_id,
            customer_name=names.get(m.reservation_id),
            attachment_ids=att_map.get(m.id, []),
            occurred_at=m.occurred_at,
            created_at=m.created_at,
        )
        for m in rows
    ]


@router.get(
    "/attachments/{attachment_id}",
    dependencies=[Depends(require_admin_or_above)],
)
async def get_attachment(
    attachment_id: int,
    db: Session = Depends(get_tenant_scoped_db),
):
    att = db.query(SmsAttachment).filter(SmsAttachment.id == attachment_id).first()
    if att is None:
        raise HTTPException(status_code=404, detail="첨부를 찾을 수 없습니다")
    return Response(
        content=att.data,
        media_type=att.content_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )


class ReplyRequest(BaseModel):
    peer_phone: str
    text: str = Field(min_length=1, max_length=2000)


@router.post(
    "/reply",
    response_model=MessageOut,
    dependencies=[Depends(require_admin_or_above)],
)
async def queue_reply(
    request: ReplyRequest,
    db: Session = Depends(get_tenant_scoped_db),
    current_user: User = Depends(get_current_user),
):
    """답장을 큐에 넣는다. 실제 발송은 폰이 가져가서 수행."""
    phone = normalize_phone(request.peer_phone)
    if not phone:
        raise HTTPException(status_code=400, detail="전화번호가 올바르지 않습니다")

    active = (
        db.query(func.count(SmsDevice.id))
        .filter(SmsDevice.is_active == True)  # noqa: E712
        .scalar()
    ) or 0
    if active == 0:
        raise HTTPException(status_code=409, detail="승인된 게이트웨이 기기가 없습니다")

    msg = SmsMessage(
        direction="out",
        peer_phone=phone,
        body=request.text,
        status="pending",
        source="system",
        reservation_id=_match_reservation(db, phone),
        created_by=current_user.username,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    diag(
        "gateway.reply.queued",
        level="critical",
        tid=msg.tenant_id,
        message_id=msg.id,
        phone=mask_phone(phone),
        actor=current_user.username,
    )
    return MessageOut(
        id=msg.id,
        direction=msg.direction,
        peer_phone=msg.peer_phone,
        body=msg.body,
        status=msg.status,
        source=msg.source,
        is_mms=msg.is_mms,
        reservation_id=msg.reservation_id,
        attachment_ids=[],
        occurred_at=msg.occurred_at,
        created_at=msg.created_at,
    )
