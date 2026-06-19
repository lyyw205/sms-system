"""party_type 단일 명세(party_type.py) 특성화 테스트.

마이그레이션 전 현재 동작을 핀으로 고정 — 이후 호출처 치환이 no-op 임을 보장한다.
값/집합관계가 바뀌면 여기서 즉시 실패한다.
"""
from app.services.party_type import (
    PARTY_JOINED_TYPES,
    PARTY3_2CHA_TYPES,
    effective_party_type,
    effective_party_type_sql,
)


def test_party_joined_types_values():
    # party_checkin.py:48 / sales_report.py:103 / filters.py:91 의 기존 리터럴과 동일
    assert set(PARTY_JOINED_TYPES) == {'1', '2', '2차만'}


def test_party3_2cha_types_values():
    # party3_mms.py:37 의 기존 리터럴과 동일
    assert set(PARTY3_2CHA_TYPES) == {'2', '2차만'}


def test_party3_is_strict_subset_of_joined():
    # 부분집합 함정 가드: PARTY3 ⊂ PARTY_JOINED 이고, '1'(1차만)은 PARTY3 에 없다.
    assert PARTY3_2CHA_TYPES < PARTY_JOINED_TYPES
    assert '1' in PARTY_JOINED_TYPES
    assert '1' not in PARTY3_2CHA_TYPES
    # 두 집합은 동일하지 않다 (절대 병합 금지)
    assert PARTY_JOINED_TYPES != PARTY3_2CHA_TYPES


def test_effective_party_type_truth_table():
    # Python 'or' 계열: None 과 '' 모두 폴백, 비어있지 않은 daily 는 채택.
    assert effective_party_type(None, '2') == '2'
    assert effective_party_type('', '2') == '2'        # '' 는 폴백
    assert effective_party_type('1', '2') == '1'       # daily 우선
    assert effective_party_type('2차만', None) == '2차만'
    assert effective_party_type(None, None) is None
    assert effective_party_type('', '') == ''          # 둘 다 falsy → reservation('') 반환


def test_effective_party_type_equivalent_to_or():
    # 명시적으로 `daily or reservation` 과 1:1 동등함을 핀.
    for daily in (None, '', '1', '2', '2차만'):
        for res in (None, '', '1', '2', '2차만'):
            assert effective_party_type(daily, res) == (daily or res)


def test_effective_party_type_sql_is_coalesce():
    # SQL 트윈은 func.coalesce 와 동일한 표현식을 생성한다 (NULL 만 폴백).
    from sqlalchemy import func, literal

    expr = effective_party_type_sql(literal('a'), literal('b'))
    expected = func.coalesce(literal('a'), literal('b'))
    # 컴파일된 SQL 텍스트가 동일 (함수명 coalesce + 인자 순서 보존)
    assert str(expr) == str(expected)
    assert 'coalesce' in str(expr).lower()
