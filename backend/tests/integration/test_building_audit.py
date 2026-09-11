"""건물 CRUD 감사 로그 검증.

배경: 2026-09-01 사건에서 건물 9개가 감사 기록 없이 삭제돼 이름조차
복구할 수 없었다. 생성/수정/삭제 전부 before/after 스냅샷이 남아야 한다.
"""
import asyncio
import json
from types import SimpleNamespace

from app.api.buildings import BuildingUpdate, delete_building, update_building
from app.db.models import ActivityLog, Building

_USER = SimpleNamespace(username="tester")


def _run(coro):
    """asyncio.run 은 루프를 닫아 get_event_loop() 기반 기존 테스트를 깨뜨린다 — 저장소 관례."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestBuildingAudit:
    def test_update_logs_before_after_with_remapped_field(self, db):
        """payload 의 `active` 가 ORM `is_active` 로 리맵된 뒤에도 before 키가 맞아야 한다."""
        b = Building(name="본관", sort_order=0)
        db.add(b)
        db.flush()
        _run(update_building(b.id, BuildingUpdate(active=False, name="본관2"), db, _USER))
        row = db.query(ActivityLog).filter(
            ActivityLog.activity_type == "building_updated").one()
        detail = json.loads(row.detail)
        assert detail["before"] == {"name": "본관", "is_active": True}
        assert detail["after"] == {"name": "본관2", "is_active": False}
        assert row.created_by == "tester"

    def test_delete_logs_full_snapshot(self, db):
        """삭제 감사에 전문 스냅샷 — 이름·순서까지 복구 가능해야 한다."""
        b = Building(name="별관", description="구관", sort_order=1)
        db.add(b)
        db.flush()
        _run(delete_building(b.id, db, _USER))
        row = db.query(ActivityLog).filter(
            ActivityLog.activity_type == "building_deleted").one()
        detail = json.loads(row.detail)
        assert detail["name"] == "별관"
        assert detail["description"] == "구관"
        assert detail["sort_order"] == 1
        assert db.query(Building).count() == 0
