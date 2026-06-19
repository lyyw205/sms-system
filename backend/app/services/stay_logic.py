"""stay_logic.py — 투숙 기간(당일 vs 숙박) 단일 판정 로직.

check_out_date 의 NULL/''/날짜 해석을 한 곳으로 모은 **leaf 모듈**.
반열림 규약 `[check_in, check_out)`: 체크아웃일은 박(night)이 아님. NULL/''/co==ci = 당일 1박.

흩어진 술어 5계열(설계 docs/plans/stay-semantics-design.md §2)을 단일화하기 위한 1단계 —
section_registry / party_type 와 동일한 "단일 명세 + 특성화 + no-op 교체" 패턴.

⚠️ leaf 제약: `datetime` 외 `app.*` import 금지.
   `date_range` 는 순환참조(room_assignment→chip_reconciler→template_scheduler→room_assignment,
   schedule_utils.py:3-6 주석)를 깨기 위해 `schedule_utils.py` 에 물리적으로 잔류한다 —
   여기서 re-export 하지 않는다(re-export 하면 stay_logic→schedule_utils→stay_logic 순환 재발).
   호출처는 `date_range` 를 기존대로 `app.services.schedule_utils` 에서 import.

⚠️ 이 헬퍼들은 **가드된(정규) 사이트**의 동작을 추출한 것이다. co<ci(손상행) 같은 경우의
   "이상하지만 현재의" 동작을 그대로 보존한다(no-op). 가드가 빠진 사이트(room_upgrade_common
   last_night co==ci 누락 등)는 별도 잠재버그 레지스터(§5 LB-02..)에서 사람 결정으로 처리.
"""
from datetime import datetime
from typing import Optional


def is_single_day_stay(check_in: Optional[str], check_out: Optional[str]) -> bool:
    """당일(1박) 여부 — `not check_out or check_out == check_in` 와 정확히 동일.

    True : check_out 이 NULL/'' 이거나 check_in 과 같을 때 (당일 1박).
    False: check_out 이 truthy 이고 check_in 과 다를 때 (연박).
           co<ci(손상)도 여기서 False(=연박 취급) — 정규 사이트(schedule_utils:25,
           template_scheduler:844)의 현행 동작 그대로 보존.
    """
    return not check_out or check_out == check_in


def stay_nights(check_in: Optional[str], check_out: Optional[str]) -> int:
    """박수 = max(1, (check_out - check_in).days). NULL/'' 또는 파싱불가 → 1.

    co<=ci(손상 포함)는 max(1, ·) 로 1박이 된다(현행 보존). 이 floor 는 돈 계산
    (_inject_surcharge_vars)을 먹이므로 절대 제거 금지 — co<ci 청구 마스킹(LB-08)은 별도 결정.
    """
    if not check_out or not check_in:
        return 1
    try:
        ci = datetime.strptime(check_in, "%Y-%m-%d")
        co = datetime.strptime(check_out, "%Y-%m-%d")
        return max(1, (co - ci).days)
    except (ValueError, TypeError):
        return 1
