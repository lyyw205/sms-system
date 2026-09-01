# 도미토리 성별충돌(gender_mix) 오판 수정 — 사전 Impact Analysis

> 상태: **사전조사 (코드 미수정)** · 작성일 2026-06-11 · 트리거: 운영 관찰
> 원칙: mutator-rigor (라인 단위 Before/After + 동작 동등성 + 시나리오 비교 후 구현)

## 0. TL;DR

- **증상**: 수동 추가한 "여자 2명" 게스트(`[tid=2] res=6747` 송현주)를 네이버 도미토리 예약(`[tid=2] res=6614` 박송희, 여1)이 점유한 B206(4인실 도미토리, bed_capacity=4)에 넣으면 **서로 밀어냄**. 둘 다 여성·정원 여유(2+1=3≤4)인데도 막힘.
- **서버 로그 확정**: `[dormitory.hardline] room_id=24 date=2026-06-12 reason=gender_mix ...` (capacity 아님).
- **근본 원인**: `Reservation.gender` 는 **표시용** 필드라 경로마다 포맷이 다름 — 네이버=`'여'`(단일 글자), 수동추가=`'여2'`(인원수 합성). 그런데 도미토리 성별충돌 판정이 이 문자열을 **등호 비교**(`a.gender != b.gender`)해서 `'여' != '여2'` → 같은 성별을 혼숙으로 오판.
- **진실원천 불일치**: 성별 구성의 실제 진실원천은 `male_count`/`female_count`. gender 문자열은 표시용(프론트가 정규식으로 파싱).
- **권장 수정**: 저장 포맷은 그대로 두고(혼성 표시 보존), **백엔드 성별판정 로직만 `male_count`/`female_count` 기반 공통 헬퍼로 전환**. 데이터 마이그레이션 불필요.

---

## 1. 근본 원인

| 경로 | `gender` 저장 포맷 | 코드 |
|------|------------------|------|
| 네이버 동기화 | 예약자 단일 성별 `'남'`/`'여'` | `naver_sync.py:818-819`, `real/reservation.py:322` |
| 수동 추가 모달 | 인원수 합성 `'여2'`, `'남1여2'` | `frontend/.../useReservationForm.ts:176-178` (`남${m}` + `여${f}`) |

`gender` 문자열은 **프론트 표시용**으로 설계됨 — `reservationFormat.ts:16-27` 이 `/남(\d+)/`·`/여(\d+)/` 정규식으로 파싱해 성별칼럼에 M/F 분해 표시. 즉 합성 포맷("남1여2")은 **혼성 인원 표시를 위해 의도된 것**이고, 단일 글자로는 혼성을 표현 못 함.

문제는 백엔드 **성별충돌 판정 로직이 이 표시용 문자열을 진실원천처럼 등호 비교**한다는 점. 성별 구성의 실제 진실원천은 `male_count`/`female_count`.

### 실데이터 (production, tid=2)

| res | 이름 | gender | M | F | section | naver_id | 출처 |
|-----|------|--------|---|---|---------|----------|------|
| 6747 | 송현주 | `'여2'` | None | 2 | unassigned | None | 수동 |
| 6614 | 박송희 | `'여'` | 0 | 1 | room | 1260308332 | 네이버 |
| 6745 | 신소현 | `'여'` | 0 | 2 | room | 1262205673 | 네이버 |

`'여2' != '여'` → `reason=gender_mix` → 밀어냄. 셋 다 여성.

---

## 2. 전체 영향 범위 — 합성 gender 포맷이 깨뜨리는 사이트 (7곳)

단일 글자 `'남'`/`'여'` 를 가정하고 비교/매칭하는 모든 사이트가 `'여2'` 에서 오작동.

| # | 사이트 | 종류 | 증상 | 이번 PR 범위 |
|---|--------|------|------|------|
| 1 | `room_assignment.py:343-350` | 도미토리 수동배정 hardline 충돌 | 같은성별 밀어냄(보고된 버그) | **In** |
| 2 | `room_auto_assign.py:414-420` | 자동배정 gender_lock | 같은성별 자동배정 차단 | **In** |
| 3 | `room_assignment_invariants.py:82-89` | 배정후 무결성 가드 | 같은성별 invariant.violation 오탐 | **In** |
| 4 | `room_auto_assign.py:265-270` `_gender_sort_key` | 자동배정 정렬 우선순위 | 수동 여성게스트가 '미상(2)'로 정렬 | P2(권장 동봉) |
| 5 | `room_auto_assign.py:354` → `_sort_candidate_rooms` | 성별별 객실 우선순위 | 수동게스트 객실 우선순위 오판 | P2(권장 동봉) |
| 6 | `api/event_sms.py:66-74` | 이벤트 SMS 성별타겟 (`gender=='여'`) | 수동 '여2' 게스트 **누락** | P3(별도) |
| 7 | `scheduler/template_scheduler.py:714-716` | 스케줄 SMS 성별필터 | 수동 '여2' 게스트 **누락** | P3(별도) |

> #6,#7 은 SMS 발송 대상 변화라 발송 안전성 검증이 별도로 필요 → 분리 권장.
> 무관(변경 안 함): `naver_sync.py:947-978`(gender 변경 감지 — 단순 같음/다름), 프론트 `reservationFormat.ts`(표시 — 합성 포맷 그대로 필요).

---

## 3. 수정 전략 비교

### 전략 A — 저장 포맷 정규화 (`useReservationForm` 가 단일글자 저장) ❌ 비권장
- 7개 사이트 한 번에 해결처럼 보이나:
  - **혼성 표시 파괴**: `'남1여2'` 를 단일글자로 못 담음 → 프론트 성별칼럼 M/F 분해 표시 깨짐.
  - 기존 `'여N'` 행 **데이터 마이그레이션** 필요.
  - gender 문자열 의미를 바꾸는 광범위 변경 → blast radius 큼.

### 전략 B — 백엔드 성별판정을 `male_count`/`female_count` 기반 공통 헬퍼로 전환 ✅ 권장
- 저장 포맷·프론트 표시 **그대로 유지**(혼성 표시 보존), **마이그레이션 0**.
- 진실원천(counts)으로 판정 → 포맷 불일치 원천 무력화.
- In-scope 3개 사이트를 공통 헬퍼 1개로 통일(코드 중복 제거).
- #4,#5 도 같은 헬퍼로 정리 가능(P2). #6,#7 은 발송영향이라 분리(P3).

> **결론: 전략 B 채택.** gender 문자열은 표시용으로 남기고, 로직은 counts 를 본다.

---

## 4. 라인 단위 Before/After (전략 B, In-scope 3사이트 + 신규 헬퍼)

### 4.0 신규 모듈 `backend/app/services/dorm_gender.py`

```python
"""도미토리 성별 충돌 판정 — 진실원천(male_count/female_count) 기반.

배경: Reservation.gender 는 표시용 필드로 경로마다 포맷이 다름.
  - 네이버: 예약자 단일 성별 '남'/'여'
  - 수동추가: 인원수 합성 '여2' / '남1여2'
따라서 gender 문자열 등호비교는 같은 성별도 포맷차로 혼숙 오판('여' vs '여2').
성별 구성의 진실원천은 male_count/female_count 이므로 이를 기준으로 판정한다.
gender 문자열은 counts 가 모두 비었을 때만 fallback 파싱.
"""
from typing import Iterable, Tuple, Optional


def gender_presence(res) -> Tuple[bool, bool]:
    """(has_male, has_female) — 예약이 도미토리에 들이는 성별 존재 여부."""
    if res is None:
        return (False, False)
    m = res.male_count or 0
    f = res.female_count or 0
    if m or f:
        return (m > 0, f > 0)
    g = (res.gender or "").strip()          # counts 없을 때만 표시문자열 파싱
    return ("남" in g, "여" in g)


def dorm_gender_conflict(new_res, others: Iterable) -> bool:
    """new_res 를 others 점유 도미토리 셀에 넣으면 남/여 혼숙이 되는가.
    혼숙 = (신규 남성포함 AND 기존 여성포함) OR (신규 여성포함 AND 기존 남성포함).
    빈 셀 / 한쪽 성별미상 → 충돌 아님 (기존 동작 보존)."""
    nm, nf = gender_presence(new_res)
    om = of = False
    for o in others:
        m, f = gender_presence(o)
        om = om or m
        of = of or f
    return (nm and of) or (nf and om)
```

### 4.1 `room_assignment.py` (Site 1)

**Before (342-350):**
```python
                # 혼성 체크
                gender_conflict = False
                if new_gender:
                    for o_ra in others:
                        o_res = other_res_map.get(o_ra.reservation_id)
                        o_gender = (o_res.gender or "").strip() if o_res else ""
                        if o_gender and o_gender != new_gender:
                            gender_conflict = True
                            break
```
**After:**
```python
                # 혼성 체크 — male/female_count 기반 (gender 문자열 포맷 불일치 회피)
                gender_conflict = dorm_gender_conflict(
                    reservation,
                    (other_res_map.get(o_ra.reservation_id) for o_ra in others),
                )
```
- 부수: `new_gender = (reservation.gender or "").strip()` (line 309) 가 이 블록 외 미사용이면 제거. → **확인 필요** (구현 시 grep). import 추가: `from app.services.dorm_gender import dorm_gender_conflict`.

### 4.2 `room_auto_assign.py` (Site 2)

**Before (414-420):**
```python
                    res_gender = (res.gender or "").strip()
                    gender_conflict = False
                    for existing_res in existing_reservations:
                        existing_gender = (existing_res.gender or "").strip()
                        if existing_gender and res_gender and existing_gender != res_gender:
                            gender_conflict = True
                            break
```
**After:**
```python
                    gender_conflict = dorm_gender_conflict(res, existing_reservations)
```
- `res_gender`(line 414)는 이 블록 전용이면 제거. line 354 의 `res_gender`(정렬용, Site 5)와 **다른 스코프**이므로 혼동 주의.

### 4.3 `room_assignment_invariants.py` (Site 3)

**Before (82-90):**
```python
            if res_gender:
                gender_conflict = False
                for o in others:
                    o_res = other_res_map.get(o.reservation_id)
                    o_gender = (o_res.gender or "").strip() if o_res else ""
                    if o_gender and o_gender != res_gender:
                        gender_conflict = True
                        break
                if gender_conflict:
```
**After:**
```python
            if dorm_gender_conflict(
                reservation,
                (other_res_map.get(o.reservation_id) for o in others),
            ):
```
- `res_gender`(line 71)는 capacity 블록에서 미사용이면 제거 가능(별도 `res_count` 는 유지). 들여쓰기 한 단계 감소 주의.

---

## 5. 동작 동등성 — 진리표 (신규 vs 기존)

`N`=신규예약 성별존재, `E`=기존점유 성별존재. 충돌=밀어냄/차단.

| 케이스 | 신규 | 기존 | 기존로직(문자열 ≠) | 신규로직(presence) | 변화 |
|--------|------|------|---------|---------|------|
| 여2 vs 여1 | F | F | 충돌('여2'≠'여') | **무충돌** | ✅ **버그수정** |
| 남2 vs 남 | M | M | 충돌('남2'≠'남') | **무충돌** | ✅ 수정 |
| 여2 vs 여3 | F | F | 충돌 | **무충돌** | ✅ 수정 |
| 남 vs 여 | M | F | 충돌 | 충돌 | = 보존 |
| 여 vs 남 | F | M | 충돌 | 충돌 | = 보존 |
| 남1여2(혼성) vs 여 | M+F | F | 충돌 | 충돌(남∧여기존) | = 보존 |
| 남1여2(혼성) vs **빈셀** | M+F | — | 무충돌(루프 안돔) | 무충돌(기존없음) | = **보존** ★ |
| 여 vs 빈셀 | F | — | 무충돌 | 무충돌 | = 보존 |
| 미상('') vs 여 | — | F | 무충돌(`if new_gender` skip) | 무충돌 | = 보존 |
| 여 vs 미상('') | F | — | 무충돌(`o_gender` falsy skip) | 무충돌 | = 보존 |

- **유일한 동작 변화 = 같은성별·포맷차 오탐(여2vs여 류)의 충돌 → 무충돌.** 정확히 의도한 수정.
- ★ 빈 도미토리에 혼성팀 단독 배정은 **기존처럼 허용**(cross-party 충돌만 봄). 자기 자신의 혼성은 충돌로 안 봄 → 운영자 의도 배정 보존.

---

## 6. 시나리오 비교 (실데이터 포함)

1. **보고된 케이스**: res=6747(여2) → B206(res=6614 여1 점유). 기존: gender_mix 밀어냄. 수정후: 무충돌, 2+1=3≤4 정원OK → **공존 배정 성공**.
2. **정원 케이스(무관 확인)**: 06-28 `reason=capacity` (res=6745 booking_count=2). 성별로직 미접촉 → 그대로 capacity 가드 동작.
3. **정상 혼숙 차단 보존**: 남성 예약을 여성 점유 도미토리에 → 여전히 차단.
4. **자동배정**: 동일 헬퍼라 수동/자동/invariant 3경로 판정 일관.

---

## 7. 사이드이펙트 / Blast Radius

- **저장 데이터 불변** → 마이그레이션 0, 롤백 단순(코드 revert).
- **프론트 표시 불변** → `reservationFormat.ts` 합성 파싱 그대로 유효.
- **무관 사이트 불변**: `naver_sync` gender 변경감지, SMS 타겟(#6,#7 — 별도 P3).
- **잠재 위험**: `male_count`/`female_count` 가 비고 gender 도 빈 예약 → presence (F,F) → 충돌판정서 제외(기존도 동일하게 skip). 동등.
- **counts 신뢰성**: 도미토리 예약은 `_init_gender_counts`(naver_sync:828)로 counts 세팅, 수동은 모달이 male/female_count 입력. 양 경로 모두 counts 채움 → 진실원천 신뢰 가능. 미세 누락은 gender 문자열 fallback 이 흡수.

---

## 8. 테스트 계획

- **단위** `tests/.../test_dorm_gender.py` (신규): §5 진리표 전 케이스 + `gender_presence` (counts 우선, gender fallback, 둘다빔).
- **통합 회귀**:
  - 여2(수동) + 여1(네이버) 같은 도미토리 공존 (보고된 버그 회귀) — 신규.
  - 남+여 차단 보존 — 기존 `test_auto_assign_failure.py:98-102` 류 유지(단일글자라 통과).
  - 혼성 빈셀 허용 / 혼성+여 차단 — 신규.
  - capacity 케이스 불변 — 기존.
- **기존 테스트 영향**: `test_auto_assign_failure.py`, `test_invariants.py`, `test_room_auto_assign.py` 는 전부 단일글자 `'남'`/`'여'` 사용 → 신규로직에서도 동일 결과 → **수정 불필요(통과 예상)**. 구현 후 실제 실행 확인.

---

## 9. 롤아웃 / 검증

1. 구현 → `cd backend && pytest tests/integration/test_room_auto_assign.py test_auto_assign_failure.py test_invariants.py tests/.../test_dorm_gender.py`.
2. diag-golden: `dormitory.hardline`/`invariant.violation` 정답지에 신규 `reason` 의미변화 반영 검토(이벤트 스키마 동일, 빈도만 감소).
3. 배포후 운영 확인: 보고 케이스 재현 → 공존 배정되는지 + `dormitory.hardline reason=gender_mix` 오발생 소거 확인.

---

## 10. 범위 확정 (구현 전 합의 필요)

- [ ] **In(필수)**: Site 1·2·3 (도미토리 성별충돌 3경로) — 보고된 버그.
- [ ] **P2 동봉?**: Site 4·5 (자동배정 정렬 우선순위) — `_gender_sort_key`/`_sort_candidate_rooms` 도 presence 기반으로. 저위험, 자동배정 품질 개선.
- [ ] **P3 별도?**: Site 6·7 (SMS 성별타겟) — 수동 '여2' 게스트가 여성타겟 SMS 누락. **발송대상 변화라 별도 PR + 발송검증** 권장.
