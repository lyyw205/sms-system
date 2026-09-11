"""객실 그룹 bulk 교체(`PUT /rooms/groups/bulk`) 검증.

배경: 2026-08-31 구분선 저장이 "전체 DELETE 후 재생성" 방식이라 그룹 13개
이름이 유실됐다. bulk 엔드포인트는 id 기준 수정/생성/삭제 + 단일 트랜잭션으로
그 재발을 막는다. 특히 "삭제되는 그룹의 객실을 다른 그룹으로 이동" 케이스는
초기 구현에서 ORM cascade nullify 가 재배정을 덮어써 유실됐던 버그의 회귀 방지.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.rooms import RoomGroupBulkItem, RoomGroupBulkRequest, replace_room_groups
from app.db.models import ActivityLog, Room, RoomGroup

_USER = SimpleNamespace(username="tester")


def _run(coro):
    """asyncio.run 은 루프를 닫아 get_event_loop() 기반 기존 테스트를 깨뜨린다
    (test_verify_tenant_access 등과 같은 세션에서 실행 시). 저장소 관례를 따른다."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _mk_rooms(db, n):
    rooms = [Room(room_number=f"R{i}", room_type="더블") for i in range(1, n + 1)]
    db.add_all(rooms)
    db.flush()
    return rooms


def _call(db, groups, user=_USER):
    req = RoomGroupBulkRequest(groups=[RoomGroupBulkItem(**g) for g in groups])
    return _run(replace_room_groups(req, db, user))


def _setup_three_groups(db):
    """그룹 3개(스위트/더블/트윈) × 방 6개, 2개씩 소속."""
    rooms = _mk_rooms(db, 6)
    g1 = RoomGroup(name="스위트", sort_order=0)
    g2 = RoomGroup(name="더블", sort_order=1)
    g3 = RoomGroup(name="트윈", sort_order=2)
    db.add_all([g1, g2, g3])
    db.flush()
    for r, g in zip(rooms, [g1, g1, g2, g2, g3, g3]):
        r.room_group_id = g.id
    db.flush()
    return rooms, g1, g2, g3


class TestBulkReplace:
    def test_id_reuse_preserves_names_and_deletes_missing(self, db):
        """id 를 실어 보내면 이름이 보존되고, 요청에 없는 그룹은 삭제된다."""
        rooms, g1, g2, g3 = _setup_three_groups(db)
        result = _call(db, [
            {"id": g1.id, "name": "스위트", "sort_order": 0,
             "room_ids": [rooms[0].id, rooms[1].id]},
            {"id": g2.id, "name": "더블A", "sort_order": 1, "room_ids": [rooms[2].id]},
        ])
        assert {g.name for g in db.query(RoomGroup).all()} == {"스위트", "더블A"}
        assert [g.name for g in result] == ["스위트", "더블A"]
        db.expire_all()
        # 어떤 그룹에도 안 실린 객실은 그룹 해제
        assert rooms[3].room_group_id is None
        assert rooms[4].room_group_id is None and rooms[5].room_group_id is None

    def test_move_room_out_of_deleted_group(self, db):
        """삭제되는 그룹의 객실을 같은 요청에서 다른 그룹으로 이동 — 유실 버그 회귀 방지.

        초기 구현은 재배치 후 db.delete() 를 실행해, 삭제 그룹의 stale rooms
        관계를 따라간 FK nullify 가 새 배정을 덮어썼다 (r5 → NULL 유실).
        """
        rooms, g1, g2, g3 = _setup_three_groups(db)
        _call(db, [
            {"id": g1.id, "name": "스위트", "sort_order": 0,
             "room_ids": [rooms[0].id, rooms[1].id, rooms[4].id]},  # r5: g3 → g1 이동
            {"id": g2.id, "name": "더블", "sort_order": 1,
             "room_ids": [rooms[2].id, rooms[3].id]},
        ])
        db.expire_all()
        assert rooms[4].room_group_id == g1.id, "삭제 그룹에서 이동한 객실의 배정 유지"
        assert rooms[5].room_group_id is None
        assert db.query(RoomGroup).count() == 2

    def test_unknown_group_id_400_and_nothing_changes(self, db):
        rooms, g1, _, _ = _setup_three_groups(db)
        with pytest.raises(HTTPException) as e:
            _call(db, [{"id": 999, "name": "X", "sort_order": 0, "room_ids": []}])
        assert e.value.status_code == 400
        assert db.query(RoomGroup).count() == 3
        assert rooms[0].room_group_id == g1.id, "검증 실패 시 기존 배치 무변경"

    def test_unknown_room_id_400(self, db):
        with pytest.raises(HTTPException) as e:
            _call(db, [{"name": "X", "sort_order": 0, "room_ids": [12345]}])
        assert e.value.status_code == 400

    def test_empty_request_deletes_all_groups(self, db):
        """구분선을 전부 지우면(그룹 1개 이하) 프론트가 빈 목록을 보낸다."""
        rooms, *_ = _setup_three_groups(db)
        assert _call(db, []) == []
        assert db.query(RoomGroup).count() == 0
        db.expire_all()
        assert all(r.room_group_id is None for r in rooms)

    def test_new_group_created_without_id(self, db):
        rooms = _mk_rooms(db, 1)
        result = _call(db, [{"name": "신규", "sort_order": 0, "room_ids": [rooms[0].id]}])
        assert len(result) == 1 and result[0].name == "신규"
        db.expire_all()
        assert rooms[0].room_group_id == result[0].id


class TestBulkReplaceAudit:
    def test_audit_log_has_before_after_snapshot(self, db):
        """8/31 복구 불능의 원인이 감사 부재 — before/after 전문이 남아야 한다."""
        rooms, g1, g2, g3 = _setup_three_groups(db)
        _call(db, [
            {"id": g1.id, "name": "스위트", "sort_order": 0, "room_ids": [rooms[0].id]},
        ])
        row = db.query(ActivityLog).filter(
            ActivityLog.activity_type == "room_group_bulk").one()
        detail = json.loads(row.detail)
        assert len(detail["before"]) == 3 and len(detail["after"]) == 1
        assert detail["removed_ids"] == sorted([g2.id, g3.id])
        assert {g["name"] for g in detail["before"]} == {"스위트", "더블", "트윈"}
        assert row.created_by == "tester"
