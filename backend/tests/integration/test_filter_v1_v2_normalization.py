"""_normalize_to_v2() idempotency 및 v1→v2 정규화 단위 테스트.

직접 import 해서 변환 결과를 검증한다 — DB 불필요.
"""
import pytest
from app.services.filters import _normalize_to_v2


class TestNormalizeToV2:
    def test_room_plus_two_buildings_merged(self):
        """[assignment:room] + [building:1] + [building:2] → buildings=[1,2] 하나로 병합."""
        inp = [
            {"type": "assignment", "value": "room"},
            {"type": "building", "value": "1"},
            {"type": "building", "value": "2"},
        ]
        out = _normalize_to_v2(inp)
        assert len(out) == 1
        assert out[0]["type"] == "assignment"
        assert out[0]["value"] == "room"
        assert sorted(out[0]["buildings"]) == [1, 2]

    def test_unassigned_plus_building_becomes_include_unassigned(self):
        """[assignment:unassigned] + [building:1] → room filter with include_unassigned=True."""
        inp = [
            {"type": "assignment", "value": "unassigned"},
            {"type": "building", "value": "1"},
        ]
        out = _normalize_to_v2(inp)
        assert len(out) == 1
        assert out[0]["type"] == "assignment"
        assert out[0]["value"] == "room"
        assert out[0].get("buildings") == [1]
        assert out[0].get("include_unassigned") is True

    def test_party_assignment_idempotent(self):
        """[assignment:party] → 변환 없이 그대로."""
        inp = [{"type": "assignment", "value": "party"}]
        out = _normalize_to_v2(inp)
        assert out == [{"type": "assignment", "value": "party"}]

    def test_ghost_room_type_dropped(self):
        """[type:room, value:'5'] → ghost drop → 빈 리스트."""
        inp = [{"type": "room", "value": "5"}]
        out = _normalize_to_v2(inp)
        assert out == []

    def test_legacy_room_assigned_alias(self):
        """[type:room_assigned] → [assignment:room]."""
        inp = [{"type": "room_assigned"}]
        out = _normalize_to_v2(inp)
        assert len(out) == 1
        assert out[0] == {"type": "assignment", "value": "room"}

    def test_legacy_party_only_alias(self):
        """[type:party_only] → [assignment:party]."""
        inp = [{"type": "party_only"}]
        out = _normalize_to_v2(inp)
        assert len(out) == 1
        assert out[0] == {"type": "assignment", "value": "party"}

    def test_v2_input_is_noop(self):
        """이미 v2 형식 입력은 변환 없이 통과 (idempotent)."""
        inp = [
            {"type": "assignment", "value": "room", "buildings": [1, 2]},
        ]
        out = _normalize_to_v2(inp)
        assert out == inp

    def test_v2_input_ghost_room_still_stripped(self):
        """v2 경로에서도 ghost type:room 은 제거."""
        inp = [
            {"type": "assignment", "value": "room", "buildings": [3]},
            {"type": "room", "value": "99"},
        ]
        out = _normalize_to_v2(inp)
        assert all(f.get("type") != "room" for f in out)
        assert len(out) == 1

    def test_empty_input_returns_empty(self):
        """빈 리스트 → 빈 리스트."""
        assert _normalize_to_v2([]) == []

    def test_column_match_preserved(self):
        """column_match 항목은 변환 영향 없이 보존."""
        inp = [
            {"type": "assignment", "value": "room"},
            {"type": "column_match", "value": "party_type:is_not_empty:"},
        ]
        out = _normalize_to_v2(inp)
        cm = [f for f in out if f.get("type") == "column_match"]
        assert len(cm) == 1
        assert cm[0]["value"] == "party_type:is_not_empty:"

    def test_standalone_unassigned_no_building(self):
        """[assignment:unassigned] 단독 (건물 없음) → peer로 유지."""
        inp = [{"type": "assignment", "value": "unassigned"}]
        out = _normalize_to_v2(inp)
        assert len(out) == 1
        assert out[0]["value"] == "unassigned"
        assert "include_unassigned" not in out[0]
