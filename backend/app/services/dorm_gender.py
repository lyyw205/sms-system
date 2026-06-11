"""도미토리 성별 판정 — 진실원천(male_count/female_count) 기반.

배경
----
`Reservation.gender` 는 **표시용** 필드라 경로마다 포맷이 다르다.
  - 네이버 동기화: 예약자 단일 성별 한 글자 ('남' / '여')      — naver_sync.py
  - 수동 추가 모달: 인원수 합성 ('여2', '남1여2')             — useReservationForm.ts
프론트는 이 합성 포맷을 정규식(`/남(\\d+)/`, `/여(\\d+)/`)으로 파싱해
성별 칼럼에 M/F 분해 표시를 한다 — 즉 합성 포맷은 표시 목적상 의도된 것이다.

따라서 gender 문자열을 등호 비교(`a.gender != b.gender`)하면 같은 성별도
포맷차로 혼숙 오판이 난다(예: '여' vs '여2'). 성별 *구성*의 진실원천은
`male_count` / `female_count` 이므로, 도미토리 로직은 이 카운트를 기준으로 판정한다.
gender 문자열은 카운트가 모두 비었을 때만 fallback 으로 파싱한다.

문서: docs/plans/dorm-gender-mix-falsepositive-fix.md
"""

from typing import Iterable, Tuple


def gender_presence(res) -> Tuple[bool, bool]:
    """(has_male, has_female) — 예약이 도미토리에 들이는 성별 존재 여부.

    male_count/female_count 우선. 둘 다 비었을 때만 gender 문자열 파싱(fallback).
    """
    if res is None:
        return (False, False)
    m = res.male_count or 0
    f = res.female_count or 0
    if m or f:
        return (m > 0, f > 0)
    g = (res.gender or "").strip()  # counts 없을 때만 표시문자열 파싱
    return ("남" in g, "여" in g)


def dorm_gender_conflict(new_res, others: Iterable) -> bool:
    """new_res 를 others 가 점유한 도미토리 셀에 넣으면 남/여 혼숙이 되는가.

    혼숙 = (신규 남성포함 AND 기존 여성포함) OR (신규 여성포함 AND 기존 남성포함).
    빈 셀(others 없음) 또는 한쪽 성별 미상이면 충돌 아님 — 기존 동작 보존.
    (자기 자신의 혼성 단독 배정은 충돌로 보지 않는다 = cross-party 만 판정.)
    """
    nm, nf = gender_presence(new_res)
    om = of = False
    for o in others:
        m, f = gender_presence(o)
        om = om or m
        of = of or f
    return (nm and of) or (nf and om)


def single_gender(res) -> str:
    """정렬/우선순위용 단일 성별 — 여성전용 '여', 남성전용 '남', 혼성/미상 ''.

    자동배정 정렬(_gender_sort_key) 및 객실 우선순위(_sort_candidate_rooms)에서
    합성 포맷('여2')도 올바른 성별 카테고리로 취급되게 정규화한다.
    """
    has_m, has_f = gender_presence(res)
    if has_f and not has_m:
        return "여"
    if has_m and not has_f:
        return "남"
    return ""
