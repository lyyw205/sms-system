"""password_display.build_prefixed_password 단위 테스트."""
from types import SimpleNamespace

from app.services.password_display import build_prefixed_password


def _room(pw):
    return SimpleNamespace(door_password=pw)


class TestBuildPrefixedPassword:
    def test_numeric_base_gets_prefix(self):
        result = build_prefixed_password(_room("404"))
        # "<random 0-9><literal 0><base>"
        assert result.endswith("404")
        assert len(result) == 5
        assert result[1] == "0"
        assert result[0].isdigit()

    def test_empty_base_returns_empty(self):
        assert build_prefixed_password(_room(None)) == ""
        assert build_prefixed_password(_room("")) == ""

    def test_non_numeric_base_returns_unchanged(self):
        """도어락 숫자 전용 안전장치 — prefix 안 붙임."""
        assert build_prefixed_password(_room("abc123")) == "abc123"
        assert build_prefixed_password(_room("pass#1")) == "pass#1"

    def test_whitespace_stripped(self):
        result = build_prefixed_password(_room("  404  "))
        assert result.endswith("404")
        assert len(result) == 5

    def test_randomness_across_calls(self):
        seen = {build_prefixed_password(_room("404")) for _ in range(50)}
        assert len(seen) > 1, "50회 호출하면 prefix 다양성 확인돼야 함"
