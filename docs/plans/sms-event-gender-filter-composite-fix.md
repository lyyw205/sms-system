# 이벤트 SMS 성별필터 합성-gender 누락 수정 — 사전 Impact Analysis

> 상태: **사전조사 (코드 미수정)** · 작성일 2026-06-11 · 원칙: mutator-rigor
> 선행: [[dorm-gender-mix-falsepositive-fix]] 와 같은 근본원인(gender 합성 포맷). 도미토리편 §2의 P3 항목 구현.

## 0. TL;DR

- **증상**: 성별 조건(`gender_filter='female'/'male'`) 이벤트 SMS 발송 시, **수동 추가 게스트가 누락**됨. 수동추가는 `gender='여2'`(합성) 인데 필터가 `Reservation.gender == '여'`(평비교)라 안 잡힘.
- **깨진 곳은 단 1곳**: `template_scheduler.py:712-716` `_get_targets_event`. 이 한 곳이 **자동 스케줄 발송 + `event_sms_hook` 즉시발송** 둘 다의 대상 선정을 담당 → 한 번 고치면 양쪽 해결.
- **이미 정상인 곳(수정 불요)**: `event_sms.py:65-77`(수동 검색 UI)은 `or_(gender==X, and_(count...))` 합성처리 이미 됨.
- **수정**: 검증된 `event_sms.py` 패턴을 그대로 이식 (남/여 대칭). 순수 가산적 — 여성전용/남성전용/null-gender+count만 추가, 혼성·반대성별 여전히 제외 (in-memory SQLite 실측 확인).
- **별도 발견(범위 외, 플래그)**: 즉시발송 훅은 sent-칩을 안 남겨(`send_single_sms` 미기록) → hook + 첫 스케줄런 **이중발송** 가능성. **기존 문제**이며 이 수정이 만든 게 아님. 본 수정은 누락(0건)→정상(1~2건) 개선이라 기존 수신자 동작 악화 없음.

## 1. 근본 원인

[[project_gender_field_display_vs_logic]] 와 동일. `Reservation.gender` 는 표시용 합성 문자열(`'여2'`, `'남1여2'`), 진실원천은 `male_count`/`female_count`. 이벤트 성별필터가 표시문자열을 평비교해 합성 게스트를 놓침.

## 2. 영향 범위 (재검증 6렌즈 + 비판 검증 결과)

| 경로 | 분류 | 처리 |
|------|------|------|
| `template_scheduler.py:712-716` `_get_targets_event` | **BROKEN** (평비교) | **수정** |
| `event_sms.py:65-77` `/search` | 이미 정상 (or_/and_) | 불변 (참조 패턴) |
| `filters.py:420-431` column_match `gender` | substring 연산자식 (count-blind, 평비교 아님) | 불변 (범위 외, 연산자 의미 보존) |
| `_get_targets_standard` | gender 필터 없음 | 불변 |
| `_check_send_condition` | 집계 비율 게이트 (이미 count 기반) | 불변 |

## 3. 라인 단위 Before/After

### 3.1 import (`template_scheduler.py:8`)
**Before:** `from sqlalchemy import or_, func`
**After:** `from sqlalchemy import or_, and_, func`
> `and_` 미import 상태 — 추가 안 하면 NameError (비판 검증이 잡은 항목).

### 3.2 성별필터 (`template_scheduler.py:712-716`)
**Before:**
```python
        # 2) 성별 필터 — 예약자 본인 기준 (Reservation.gender)
        if schedule.gender_filter == 'male':
            query = query.filter(Reservation.gender == '남')
        elif schedule.gender_filter == 'female':
            query = query.filter(Reservation.gender == '여')
```
**After:**
```python
        # 2) 성별 필터 — male/female_count 기반 (gender 문자열 '여2' 합성 포맷 누락 회피)
        #    event_sms.py /search 와 동일 패턴: 표시문자열 OR (해당 성별 count>0 AND 반대 count 없음)
        if schedule.gender_filter == 'male':
            query = query.filter(or_(
                Reservation.gender == '남',
                and_(Reservation.male_count.isnot(None), Reservation.male_count > 0,
                     (Reservation.female_count.is_(None) | (Reservation.female_count == 0))),
            ))
        elif schedule.gender_filter == 'female':
            query = query.filter(or_(
                Reservation.gender == '여',
                and_(Reservation.female_count.isnot(None), Reservation.female_count > 0,
                     (Reservation.male_count.is_(None) | (Reservation.male_count == 0))),
            ))
```

## 4. 동작 분석 (실측 — in-memory SQLite, 재검증 lens E)

`gender_filter='female'` 기준:

| 예약 | gender | M/F | 기존 | 신규 | 비고 |
|------|--------|-----|------|------|------|
| 네이버 여 | `'여'` | 0/1 | 포함 | 포함 | 동일 (or_ 1번째 가지) |
| 수동 여2 | `'여2'` | None/2 | **누락** | **포함** | ★ 버그 수정 |
| 수동 여1 | `'여1'` | 0/1 | 누락 | 포함 | 수정 |
| 네이버 남 | `'남'` | 1/0 | 제외 | 제외 | 동일 |
| 혼성 | `'남1여1'` | 1/1 | 제외 | **제외** | male_count>0 가드가 차단 |

→ **순수 가산적**: 누락됐던 여성전용만 추가, 혼성·남성은 그대로 제외. (남성필터 대칭 동일.)

## 5. 안전장치 / 부작용

- **중복발송 가드**: `exclude_sent`(sent_at/failed 칩, `template_scheduler.py:742-753`)가 gender 필터 *뒤*에 작동 → 이미 발송된 사람 재발송 차단. 스케줄런은 발송 후 `record_sent`(L202)로 칩 기록.
- **저장 데이터 불변**, 프론트 불변, 롤백 = 코드 revert.
- **무관 경로 불변**: 표준/커스텀 스케줄, 비율 게이트, column_match.

## 6. ⚠️ 별도 발견 (범위 외, 플래그 — 본 수정과 독립)

`event_sms_hook._send_one → send_single_sms` 는 **sent-칩을 기록하지 않음** (`sms_sender.py` 미기록 확인). 이벤트 스케줄은 타이머 등록되고(`schedule_manager` 전 활성 스케줄 등록) 스케줄런은 `record_sent` 기록.
→ **즉시발송(훅) 후 첫 스케줄런이 같은 게스트를 재발송**할 수 있음 (훅 발송엔 칩이 없으므로 dedup 미적용).

- **이것은 기존(pre-existing) 문제**로 단순 `'남'/'여'` 게스트에도 이미 적용됨. 본 gender 수정이 만든 게 아님.
- 본 수정 영향: 합성-여성 게스트가 0건 → 1~2건(타인과 동일). 기존 수신자 동작은 불변.
- **권장 후속(별도 PR + 발송검증)**: 훅 성공 시 `record_sent` 기록하거나, 이벤트의 hook/scheduler 역할 정리. 본 PR 범위에서는 제외.

## 7. 테스트 계획

`tests/integration/test_get_targets_event.py`:
- **선결 복구**: 실패 3건(`test_within_hours`, `test_gender_filter_male_only`, `test_gender_filter_female_only`)은 `check_in=today` 라 `check_in_date > today` 가드에 걸려 gender 닿기 전 빈 리스트 → **미래 날짜(today+3)로 교체**. (기존 깨짐, gender 무관.)
- **헬퍼 확장**: `_make_reservation` 에 `male_count`/`female_count` 파라미터 추가.
- **신규 단언**: female 필터 → `'여2'`(fc=2,mc=None) 포함, 혼성 `'남1여1'`(mc=1,fc=1) 제외; male 필터 대칭.

## 8. 검증/배포

1. `pytest tests/integration/test_get_targets_event.py` 그린.
2. 전체 스위트에서 신규 실패 0 확인 (기존 무관 실패만 잔존).
3. diag-golden: 이벤트 발송 빈도 증가(합성-여성 추가) — 정답지 이벤트 시퀀스 영향 없음(분기 동일, 대상 수만 증가).
