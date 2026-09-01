"""객실 설정 보호 게이트웨이 — 테넌트 스위치 (template_guard 의 객실판).

`Tenant.room_settings_locked=True` 면 그 펜션의 객실·객실그룹·건물·네이버 상품
메타에 대한 웹 수정·삭제를 차단한다. 관문 철학은 template_guard 와 동일:
"약속이 아니라, 우회하면 터지게".

예외 (잠겨 있어도 허용):
  - 객실 활성/비활성: PUT 페이로드가 is_active 만 담은 경우
  - 노출/미노출 토글(hide/unhide 엔드포인트) — 단 잠금 상태에서
    미래 배정이 있는 방의 숨김은 거부한다. 숨김은 미래 배정을 삭제하는
    파괴적 부작용을 갖기 때문 (2026-09-01 사건의 실제 피해 경로).

테넌트 컨텍스트가 없는 세션(스케줄러 잡·마이그레이션)은 관문 대상이 아니다 —
이 관문의 목적은 "웹 API 를 통한 설정 파괴" 차단이지 내부 로직 차단이 아니다.

해제는 DB 직접 변경으로만 한다 — UI 에 해제 경로를 두지 않는 것이 설계 의도.
배경: 2026-09-01 스테이블 객실 55개 파괴 사건. 잠금이 있던 템플릿·스케줄은
활성 토글 피해에 그쳤고(원복 5분), 잠금이 없던 객실 설정은 전파괴됐다(복구 반나절).
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Tenant
from app.db.tenant_context import get_session_tenant_id

_LOCKED_MSG = (
    "객실 설정이 잠겨 있습니다. 사고 재발 방지를 위해 웹에서 "
    "객실·그룹·건물·상품 정보를 수정·삭제할 수 없습니다 (활성/노출 토글 제외). "
    "변경이 필요하면 관리자에게 요청하세요."
)

# 잠겨 있어도 허용하는 PUT 필드 — 발송 on/off 와 같은 논리의 운영 토글
_ACTIVATION_ONLY = {"is_active"}


def is_room_settings_locked(db: Session) -> bool:
    tid = get_session_tenant_id(db)
    if tid is None:
        return False
    tenant = db.query(Tenant).filter(Tenant.id == tid).first()
    return bool(tenant and getattr(tenant, "room_settings_locked", False))


def assert_settings_unlocked(db: Session) -> None:
    """객실·그룹·건물·상품메타의 생성/수정/삭제 공통 관문."""
    if is_room_settings_locked(db):
        raise HTTPException(status_code=403, detail=_LOCKED_MSG)


def assert_room_update_allowed(db: Session, update_data: dict) -> None:
    """객실 PUT 관문 — is_active 단독 토글만 예외."""
    if not is_room_settings_locked(db):
        return
    touched = set(update_data.keys())
    if touched and touched <= _ACTIVATION_ONLY:
        return
    raise HTTPException(status_code=403, detail=_LOCKED_MSG)


def assert_room_hide_allowed(db: Session, future_count: int) -> None:
    """숨김 토글은 허용하되, 잠금 상태에서 미래 배정 삭제를 동반하면 거부."""
    if future_count and is_room_settings_locked(db):
        raise HTTPException(
            status_code=403,
            detail=(
                f"잠금 상태에서는 미래 배정 {future_count}건이 있는 객실을 숨길 수 없습니다. "
                "먼저 손님을 다른 방으로 옮긴 뒤 숨겨주세요."
            ),
        )
