"""객실 설정 잠금(테넌트 스위치) 가드 검증.

배경: 2026-09-01 스테이블 객실 55개 파괴 사건. template_guard 가 지킨
템플릿·스케줄은 활성 토글 피해에 그쳤고, 무방비였던 객실 설정은 전파괴됐다.
room_guard 는 같은 관문을 객실·그룹·건물·상품메타로 확장한다.

핵심 안전성 계약: 스위치 OFF(기본값)면 모든 가드가 no-op — 기존 동작 무영향.
"""
import pytest
from fastapi import HTTPException

from app.db.models import Tenant
from app.services.room_guard import (
    assert_room_hide_allowed,
    assert_room_update_allowed,
    assert_settings_unlocked,
    is_room_settings_locked,
)


def _set_lock(db, locked: bool):
    tenant = db.query(Tenant).filter(Tenant.id == 1).first()
    tenant.room_settings_locked = locked
    db.flush()


class TestUnlockedIsNoop:
    """스위치 OFF = 완전 무영향 — 배포 직후 기본 상태의 안전성 계약."""

    def test_default_off(self, db):
        assert is_room_settings_locked(db) is False

    def test_all_guards_pass_when_off(self, db):
        assert assert_settings_unlocked(db) is None
        assert assert_room_update_allowed(db, {"room_number": "A1", "grade": 3}) is None
        assert assert_room_hide_allowed(db, future_count=5) is None


class TestLockedBlocks:
    def test_settings_blocked_403(self, db):
        _set_lock(db, True)
        with pytest.raises(HTTPException) as e:
            assert_settings_unlocked(db)
        assert e.value.status_code == 403
        assert "잠겨" in e.value.detail

    def test_room_update_blocked(self, db):
        _set_lock(db, True)
        with pytest.raises(HTTPException):
            assert_room_update_allowed(db, {"room_number": "A1"})

    def test_activation_only_toggle_allowed(self, db):
        _set_lock(db, True)
        assert assert_room_update_allowed(db, {"is_active": False}) is None

    def test_activation_plus_other_field_blocked(self, db):
        _set_lock(db, True)
        with pytest.raises(HTTPException):
            assert_room_update_allowed(db, {"is_active": False, "grade": 5})

    def test_hide_with_future_assignments_blocked(self, db):
        _set_lock(db, True)
        with pytest.raises(HTTPException) as e:
            assert_room_hide_allowed(db, future_count=1)
        assert "먼저 손님" in e.value.detail

    def test_hide_without_future_assignments_allowed(self, db):
        _set_lock(db, True)
        assert assert_room_hide_allowed(db, future_count=0) is None


class TestNoTenantContext:
    """테넌트 컨텍스트 없는 세션(잡·마이그레이션)은 관문 대상 아님 —
    이 관문은 웹 API 차단이 목적이고 내부 로직을 막으면 안 된다 (의도된 통과)."""

    def test_no_context_session_not_locked(self, db):
        _set_lock(db, True)
        db.info.pop("tenant_id", None)
        try:
            assert is_room_settings_locked(db) is False
        finally:
            db.info["tenant_id"] = 1
