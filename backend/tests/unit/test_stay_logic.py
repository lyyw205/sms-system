"""stay_logic 특성화 테스트.

마이그레이션 전 현재(정규 사이트) 동작을 핀으로 고정 — 이후 호출처 치환이 no-op 임을 보장한다.
코너케이스(NULL, '', co==ci, co<ci, 비패딩)의 *현재* 출력을 박제한다.
"""
from app.services.stay_logic import is_single_day_stay, stay_nights


class TestIsSingleDayStay:
    def test_null_checkout_is_single(self):
        assert is_single_day_stay('2026-06-19', None) is True

    def test_empty_checkout_is_single(self):
        # '' 은 truthiness 상 NULL 과 동일(당일) — 정규 사이트와 일치
        assert is_single_day_stay('2026-06-19', '') is True

    def test_same_day_is_single(self):
        assert is_single_day_stay('2026-06-19', '2026-06-19') is True

    def test_multi_day_is_not_single(self):
        assert is_single_day_stay('2026-06-19', '2026-06-20') is False

    def test_corrupt_co_before_ci_is_multi(self):
        # co<ci 손상행: not co=False, co==ci=False → False(연박 취급). 현행 동작 보존.
        assert is_single_day_stay('2026-06-19', '2026-06-10') is False

    def test_equivalent_to_inline_predicate(self):
        # `not check_out or check_out == check_in` 와 1:1 동등 핀
        for ci in (None, '', '2026-06-19'):
            for co in (None, '', '2026-06-19', '2026-06-20', '2026-06-10'):
                assert is_single_day_stay(ci, co) == (not co or co == ci)


class TestStayNights:
    def test_null_checkout_is_one(self):
        assert stay_nights('2026-06-19', None) == 1

    def test_empty_checkout_is_one(self):
        assert stay_nights('2026-06-19', '') == 1

    def test_null_checkin_is_one(self):
        assert stay_nights(None, '2026-06-22') == 1

    def test_same_day_is_one(self):
        # max(1, 0) = 1
        assert stay_nights('2026-06-19', '2026-06-19') == 1

    def test_three_nights(self):
        assert stay_nights('2026-06-19', '2026-06-22') == 3

    def test_corrupt_co_before_ci_floors_to_one(self):
        # max(1, 음수) = 1 — co<ci 청구 마스킹(LB-08)의 현행 동작 보존
        assert stay_nights('2026-06-19', '2026-06-10') == 1

    def test_unparseable_returns_one(self):
        # strptime ValueError → 1
        assert stay_nights('bad', 'date') == 1

    def test_typeerror_input_returns_one(self):
        # 비-str(예: int) 입력 → TypeError → 1.
        # event_sms 는 ValueError 만 잡지만, 거기 입력은 항상 str|None(truthy 가드)이라
        # TypeError 경로가 unreachable → 광역 except 가 도달 동작을 바꾸지 않음을 증명.
        assert stay_nights(20260619, 20260622) == 1


def test_single_day_and_nights_agree_on_one_night():
    # 당일 케이스는 nights==1 과 일관
    for co in (None, '', '2026-06-19'):
        assert is_single_day_stay('2026-06-19', co) is True
        assert stay_nights('2026-06-19', co) == 1
