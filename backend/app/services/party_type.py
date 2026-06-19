"""party_type 도메인 단일 명세 — 파티참여 집합 + effective(일자별 override) 계산.

흩어져 있던 파티타입 정의를 한 곳으로 모은 명세서 (section_registry.py 와 같은 취지):
"파티 참여 기준"이나 "override 폴백 규칙"을 바꿀 때 체크할 곳을 여기 한 곳으로 줄인다.

party_type 도메인 값:
  '1'   = 1차만
  '2'   = 1+2차
  '2차만' = 2차만
  NULL / '' = 파티 미참여

────────────────────────────────────────────────────────────────────────
⚠️ 두 집합은 의미가 다르므로 절대 병합 금지 (부분집합 함정):
  - PARTY_JOINED_TYPES {'1','2','2차만'} : 파티 참여(아무 차수)
        → 통계 합산 / 스테이블 체크인 명단 / 매출 참여인원 / 필터(activity_stats_filter)
  - PARTY3_2CHA_TYPES  {'2','2차만'}      : 2차 참여만 ('1' 제외)
        → party3 당일 안내 MMS 대상 전용
  PARTY3_2CHA_TYPES 는 PARTY_JOINED_TYPES 의 진부분집합('1' 빠짐).
  narrow→wide 병합 시 1차만 게스트에게 party3 오발송, wide→narrow 병합 시 통계 누락.

⚠️ effective(override>fallback) 의 '' 처리가 호출처마다 다르다 — 의도된 기존 동작, 통일 금지:
  - effective_party_type()     : Python truthy — None 과 '' 모두 폴백
        (party_checkin / party3_mms / sales_report 의 'or' 계열)
  - effective_party_type_sql() : SQL coalesce — NULL 만 폴백, '' 는 그대로 채택
        (filters.activity_stats_filter / column_match 통계 레이어)
  - _to_response 의 `override if override is not None else res.party_type`
        : `is not None` — None 만 폴백, '' 채택 (그리드 표시용 단일 사이트라 여기 미수록,
          reservations_shared.py 주석으로 이 모듈을 가리킴)
────────────────────────────────────────────────────────────────────────
"""
from sqlalchemy import func

# 파티 참여(아무 차수) — 통계/체크인/매출/필터 공통 기준
PARTY_JOINED_TYPES = frozenset({'1', '2', '2차만'})

# 2차 참여만 — party3 당일 MMS 전용 (PARTY_JOINED_TYPES 의 진부분집합, '1' 제외)
PARTY3_2CHA_TYPES = frozenset({'2', '2차만'})


def effective_party_type(daily_value, reservation_value):
    """일자별 override(daily) 우선, 없으면 예약 기본값 — Python truthy 폴백.

    `daily_value or reservation_value` 와 정확히 동일: None 과 '' 모두 폴백한다.
    party_checkin / party3_mms / sales_report 의 'or' 계열 단일화.
    (SQL 레이어는 effective_party_type_sql 사용 — '' 처리가 다름.)
    """
    return daily_value or reservation_value


def effective_party_type_sql(daily_col, reservation_col):
    """effective_party_type 의 SQL 트윈 — `func.coalesce(daily, reservation)`.

    NULL 만 폴백하고 '' 는 그대로 채택한다(Python 'or' 와 의도적으로 다름).
    filters.activity_stats_filter / column_match 통계 레이어 전용.
    """
    return func.coalesce(daily_col, reservation_col)
