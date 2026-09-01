"""dorm_gender 단위 테스트 — 진리표 (docs/plans/_archive/dorm-gender-mix-falsepositive-fix.md §5).

핵심 회귀: 같은 성별이지만 gender 문자열 포맷이 다른 두 예약
('여'(네이버) vs '여2'(수동))이 도미토리에서 혼숙 오판되지 않아야 한다.
"""
from types import SimpleNamespace

from app.services.dorm_gender import (
    gender_presence,
    dorm_gender_conflict,
    single_gender,
)


def _r(gender=None, m=None, f=None):
    """male_count/female_count/gender 만 가진 경량 예약 스텁."""
    return SimpleNamespace(gender=gender, male_count=m, female_count=f)


# ── gender_presence: counts 우선, gender 문자열 fallback ──────────────────

class TestGenderPresence:
    def test_counts_take_priority(self):
        assert gender_presence(_r(gender="여2", m=0, f=2)) == (False, True)
        assert gender_presence(_r(gender="남", m=1, f=0)) == (True, False)
        assert gender_presence(_r(gender=None, m=1, f=2)) == (True, True)

    def test_fallback_to_gender_string_when_counts_empty(self):
        assert gender_presence(_r(gender="여", m=None, f=None)) == (False, True)
        assert gender_presence(_r(gender="남", m=0, f=0)) == (True, False)
        assert gender_presence(_r(gender="여2", m=None, f=None)) == (False, True)
        assert gender_presence(_r(gender="남1여2", m=None, f=None)) == (True, True)

    def test_empty(self):
        assert gender_presence(_r()) == (False, False)
        assert gender_presence(None) == (False, False)


# ── dorm_gender_conflict: 진리표 ──────────────────────────────────────────

class TestDormGenderConflict:
    def test_same_gender_different_format_no_conflict(self):
        """★ 보고된 버그: 여2(수동) vs 여(네이버) → 혼숙 아님."""
        new = _r(gender="여2", m=0, f=2)        # 수동 여2
        existing = _r(gender="여", m=0, f=1)     # 네이버 여1
        assert dorm_gender_conflict(new, [existing]) is False

    def test_same_gender_different_counts_no_conflict(self):
        """여2 vs 여3 도 같은 성별 → 혼숙 아님."""
        assert dorm_gender_conflict(_r(f=2), [_r(f=3)]) is False

    def test_both_male_no_conflict(self):
        assert dorm_gender_conflict(_r(gender="남2", m=2), [_r(gender="남", m=1)]) is False

    def test_male_vs_female_conflict_preserved(self):
        assert dorm_gender_conflict(_r(m=1), [_r(f=1)]) is True
        assert dorm_gender_conflict(_r(f=1), [_r(m=1)]) is True

    def test_mixed_party_vs_female_conflict(self):
        """혼성팀(남1여2)을 여성 점유 도미토리에 → 혼숙."""
        assert dorm_gender_conflict(_r(m=1, f=2), [_r(f=1)]) is True

    def test_mixed_party_into_empty_room_allowed(self):
        """빈 도미토리에 혼성팀 단독 배정은 기존처럼 허용 (cross-party만 판정)."""
        assert dorm_gender_conflict(_r(m=1, f=2), []) is False

    def test_empty_room_never_conflicts(self):
        assert dorm_gender_conflict(_r(f=2), []) is False
        assert dorm_gender_conflict(_r(m=2), []) is False

    def test_unknown_gender_no_conflict(self):
        """한쪽 성별 미상이면 충돌로 보지 않음 (기존 skip 동작 보존)."""
        assert dorm_gender_conflict(_r(), [_r(f=1)]) is False
        assert dorm_gender_conflict(_r(f=1), [_r()]) is False

    def test_multiple_others_any_opposite_triggers(self):
        new = _r(f=2)
        others = [_r(f=1), _r(m=1)]   # 기존 점유자 중 남성 존재
        assert dorm_gender_conflict(new, others) is True


# ── single_gender: 정렬/우선순위용 정규화 ─────────────────────────────────

class TestSingleGender:
    def test_normalizes_composite(self):
        assert single_gender(_r(gender="여2", m=0, f=2)) == "여"
        assert single_gender(_r(gender="남1", m=1, f=0)) == "남"

    def test_single_char_passthrough(self):
        assert single_gender(_r(gender="여", f=1)) == "여"
        assert single_gender(_r(gender="남", m=1)) == "남"

    def test_mixed_and_unknown_empty(self):
        assert single_gender(_r(m=1, f=2)) == ""
        assert single_gender(_r()) == ""
        assert single_gender(_r(gender="남1여2")) == ""
