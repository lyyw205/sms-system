# 스케줄 필터 확장 (Schedule Filter Expansion) v3

**생성일**: 2026-03-22
**최종 수정**: 2026-03-23 (is_last_in_group 통합 + stay_filter 단일화)
**상태**: 확정 대기
**복잡도**: MEDIUM (DB 6컬럼 추가, 백엔드 7파일, 프론트 1파일)

---

## Context

현재 스케줄 설정이 6개 필터(date_mode, date_filter, csf, nsf, target_mode, once_per_stay)로 144가지 조합을 만들지만 유효한 건 46가지뿐. 중복·모순·공집합이 다수 존재.

재설계 원칙:
1. **날짜 통합**: date_mode + date_filter 2개 → `date_target` 1개
2. **연박 처리 분리**: 기본 필터와 연박 처리를 별도 섹션으로 분리
3. **연박·연장 통합**: 연박자/연장자 2개 설정 → `stay_filter` 1개 (3옵션)
4. **is_last_in_group 사전 계산**: 런타임 서브쿼리 제거, 연박 감지 시 미리 저장

### 핵심 개선: 연박·연장 코드 통합

**Before**: 연박자는 필드 확인(O(1)), 연장자는 런타임 서브쿼리(O(N))
**After**: 둘 다 필드 확인(O(1)) — `is_last_in_group`을 연박 감지 시 미리 계산

```
연박 감지 시 (consecutive_stay.py — 이미 체인 순서를 알고 있음):
  for order, res in enumerate(chain):
      res.stay_group_id = group_id
      res.stay_group_order = order
      res.is_last_in_group = (order == len(chain) - 1)  ← 1줄 추가

스케줄 실행 시 (template_scheduler.py — 필드 확인만):
  if stay_filter == 'exclude':    → not r.stay_group_id
  if stay_filter == 'last_only':  → not r.stay_group_id or r.is_last_in_group
```

### 대상 시나리오

| # | 문자 | 시간 | 핵심 요구사항 |
|---|------|------|---------------|
| 1 | 파티 안내 | 12시 | 당일 전체, 인원 총합+20 후 10명 단위 올림 |
| 2 | 성비자랑 + 연박유도 | 23시 | 당일 투숙 중 연박자 제외, 내일 성비 표시, 성비에 따라 버퍼 다름 |
| 3 | 여자 연박유도 | 9시 | 오늘 체크아웃하는 여자, 이미 연장한 사람 제외 |
| 4 | 남자 연박유도 | 10시 | 오늘 체크아웃하는 남자, 이미 연장한 사람 제외 |
| 5 | 파티 미신청 독려 | 15시 | 현재 필터로 이미 가능 |

---

## 재설계: Before → After

### 스케줄 모달 구조

```
Before (설정 6개, 144조합, 유효 46개):
  ─── 발송 대상 필터 ───
  건물 / 배정 / 컬럼 조건
  날짜 기준:   [체크인] [체크아웃]
  날짜:        [오늘] [내일]
  연박자:      [전체] [연박제외] [연박만]
  연장 여부:   [전체] [연장자제외] [연장자만]
  ─── 연박자 발송 설정 ───
  [한번만] [매일]
  once_per_stay: [OFF] [ON]

After (설정 3개, 12조합, 전부 유효):
  ─── 발송 대상 필터 ───
  건물 / 배정 / 컬럼 조건
  대상 날짜:   [오늘] [내일] [오늘 체크아웃] [내일 체크아웃]
  ─── 연박 처리 ───
  연박자에게:  [그대로 발송] [발송 안함] [마지막만 발송]
  발송 빈도:   [한번만] [매일발송]
```

### 연박 상태 3가지 (is_last_in_group 기반)

```
예약A(3/20~22) ─→ 예약B(3/22~24) ─→ 예약C(3/24~26)

예약A: stay_group_id="abc", order=0, is_last=false  → 연박 계속중
예약B: stay_group_id="abc", order=1, is_last=false  → 연박 계속중
예약C: stay_group_id="abc", order=2, is_last=true   → 연박 마지막
영희:  stay_group_id=NULL                            → 단독
```

### stay_filter 3가지 동작

| stay_filter | 코드 | 남는 사람 | 용도 |
|-------------|------|-----------|------|
| null (그대로) | 필터 없음 | 전부 | 파티안내 |
| 'exclude' (발송 안함) | `not r.stay_group_id` | 단독만 | 성비자랑 |
| 'last_only' (마지막만) | `not r.stay_group_id or r.is_last_in_group` | 단독 + 마지막 | 연박유도 |

### 조합 검증 (12가지 전부 유효)

| 대상 날짜 | stay_filter | 빈도 | 판정 |
|-----------|-------------|------|------|
| 오늘/내일/체크아웃 (4) | 그대로 (null) | 한번만 | ✅ |
| 오늘/내일/체크아웃 (4) | 그대로 (null) | 매일 | ✅ |
| 오늘/내일/체크아웃 (4) | 발송안함 (exclude) | 한번만 | ✅ |
| 오늘/내일/체크아웃 (4) | 발송안함 (exclude) | 매일 | ✅ |
| 오늘/내일/체크아웃 (4) | 마지막만 (last_only) | 한번만 | ✅ |
| 오늘/내일/체크아웃 (4) | 마지막만 (last_only) | 매일 | ✅ |

**공집합 0, 모순 0, 중복 0.**

### 케이스별 설정 맵핑

| 시나리오 | 대상 날짜 | 연박자에게 | 빈도 |
|----------|-----------|-----------|------|
| 파티안내 | 오늘 | 그대로 발송 | 한번만 |
| 성비자랑 | 오늘 | 발송 안함 | 한번만 |
| 여자연박유도 | 오늘 체크아웃 | 마지막만 발송 | 한번만 |
| 남자연박유도 | 오늘 체크아웃 | 마지막만 발송 | 한번만 |
| 파티독려 | 오늘 | 그대로 발송 | 한번만 |

---

## Work Objectives

1. Reservation에 `is_last_in_group` 컬럼 추가 + consecutive_stay.py에서 사전 계산
2. TemplateSchedule에 `date_target`, `stay_filter` 컬럼 추가 (2개)
3. MessageTemplate에 `male_buffer`, `female_buffer`, `gender_ratio_buffers`, `round_unit` 컬럼 추가 (4개)
4. 기존 `date_filter` + `date_mode` → `date_target`으로 통합 (하위 호환 유지)
5. 버퍼 우선순위 로직: `gender_ratio_buffers > male/female_buffer > participant_buffer`
6. 날짜 프리픽스 변수 9개 추가 — 버퍼/반올림 동일 적용
7. custom_vars 전파 3곳 동기화
8. 프론트엔드 UI — 기본 필터 + 연박 처리 분리 구조

## Guardrails

### Must Have
- 기존 스케줄/템플릿의 동작이 변경되지 않을 것
- `is_last_in_group`은 연박 감지 시 자동 계산 (멱등)
- `round_unit`은 `total_count`에만 적용
- 성비 동점(남 == 여) 시 `female_high` 적용
- 프리픽스 변수에도 버퍼/반올림 동일 적용
- API 입력값 검증 (Literal 타입)

### Must NOT Have
- 기존 `date_filter`, `target_mode`, `once_per_stay` 컬럼 삭제 금지 (하위 호환)
- 새 DB 테이블 생성 금지
- 런타임 서브쿼리로 연장자 판정 금지 (is_last_in_group 사용)

---

## Task Flow

```
Step 1 (DB 모델 + 마이그레이션 + consecutive_stay.py)
  ↓
Step 2 (백엔드 API 스키마)
  ↓
Step 3 (필터 엔진: date_target + stay_filter)
  ↓
Step 4 (변수 계산: 버퍼 헬퍼 + 프리픽스 변수)
  ↓
Step 5 (프론트엔드 UI — 기본 필터 + 연박 처리 분리)
```

---

## Step 1: DB 모델 + Auto-Migration + 연박 감지 확장

### 수정 파일
- `backend/app/db/models.py`
- `backend/app/db/database.py`
- `backend/app/services/consecutive_stay.py`

### 1-A. Reservation 모델 — 1개 컬럼 추가

`stay_group_order` 아래에 추가:

```python
is_last_in_group = Column(Boolean, nullable=True)  # True: 연박 그룹의 마지막 예약
```

### 1-B. MessageTemplate 모델 — 4개 컬럼 추가

`participant_buffer` 아래에 추가:

```python
male_buffer = Column(Integer, default=0)           # 남성 인원 버퍼 (+N명)
female_buffer = Column(Integer, default=0)          # 여성 인원 버퍼 (+N명)
gender_ratio_buffers = Column(Text, nullable=True)  # JSON: {"male_high": {"m": 2, "f": 6}, "female_high": {"m": 6, "f": 6}}
round_unit = Column(Integer, default=0)             # 반올림 단위 (0=미사용, 10=10명 단위 올림)
```

### 1-C. TemplateSchedule 모델 — 2개 컬럼 추가

`once_per_stay` 아래에 추가:

```python
date_target = Column(String(30), nullable=True)   # 'today' | 'tomorrow' | 'today_checkout' | 'tomorrow_checkout'
stay_filter = Column(String(20), nullable=True)    # null(그대로) | 'exclude'(발송안함) | 'last_only'(마지막만)
```

**기존 컬럼과의 관계:**
- `date_target`이 설정되면 기존 `date_filter` + `date_mode`보다 우선
- `date_target`이 NULL이면 기존 `date_filter` 폴백 (하위 호환)
- `stay_filter`는 기존 `consecutive_stay_filter` + `next_stay_filter`를 통합 대체
- 기존 `target_mode`('once'/'daily')는 그대로 유지 (발송 빈도)

### 1-D. Auto-Migration (`database.py`)

```python
# reservations: is_last_in_group
if "reservations" in inspector.get_table_names():
    cols = [c["name"] for c in inspector.get_columns("reservations")]
    if "is_last_in_group" not in cols:
        conn.execute(text("ALTER TABLE reservations ADD COLUMN is_last_in_group BOOLEAN"))

# message_templates: male_buffer, female_buffer, gender_ratio_buffers, round_unit
if "message_templates" in inspector.get_table_names():
    cols = [c["name"] for c in inspector.get_columns("message_templates")]
    if "male_buffer" not in cols:
        conn.execute(text("ALTER TABLE message_templates ADD COLUMN male_buffer INTEGER DEFAULT 0"))
    if "female_buffer" not in cols:
        conn.execute(text("ALTER TABLE message_templates ADD COLUMN female_buffer INTEGER DEFAULT 0"))
    if "gender_ratio_buffers" not in cols:
        conn.execute(text("ALTER TABLE message_templates ADD COLUMN gender_ratio_buffers TEXT"))
    if "round_unit" not in cols:
        conn.execute(text("ALTER TABLE message_templates ADD COLUMN round_unit INTEGER DEFAULT 0"))

# template_schedules: date_target, stay_filter
if "template_schedules" in inspector.get_table_names():
    cols = [c["name"] for c in inspector.get_columns("template_schedules")]
    if "date_target" not in cols:
        conn.execute(text("ALTER TABLE template_schedules ADD COLUMN date_target VARCHAR(30)"))
    if "stay_filter" not in cols:
        conn.execute(text("ALTER TABLE template_schedules ADD COLUMN stay_filter VARCHAR(20)"))
```

### 1-E. consecutive_stay.py — is_last_in_group 사전 계산

`detect_and_link_consecutive_stays()` 함수의 체인 할당 루프 (line 137~142) 수정:

```python
# Before:
for order, res in enumerate(chain):
    should_be_grouped.add(res.id)
    if res.stay_group_id != group_id or res.stay_group_order != order:
        res.stay_group_id = group_id
        res.stay_group_order = order
        linked_count += 1

# After:
for order, res in enumerate(chain):
    should_be_grouped.add(res.id)
    is_last = (order == len(chain) - 1)
    if res.stay_group_id != group_id or res.stay_group_order != order or res.is_last_in_group != is_last:
        res.stay_group_id = group_id
        res.stay_group_order = order
        res.is_last_in_group = is_last
        linked_count += 1
```

그룹 해제 시 (line 146~149) is_last_in_group도 초기화:

```python
if res.stay_group_id and res.id not in should_be_grouped:
    res.stay_group_id = None
    res.stay_group_order = None
    res.is_last_in_group = None
    unlinked_count += 1
```

`unlink_from_group()`, `link_reservations()` 함수도 동일하게 is_last_in_group 반영.

### Acceptance Criteria
- [ ] 서버 재시작 시 기존 DB에 7개 컬럼 자동 추가
- [ ] 연박 감지 실행 후 is_last_in_group이 정확히 설정됨
- [ ] 그룹 해제 시 is_last_in_group = NULL로 초기화
- [ ] 기존 데이터: date_target=NULL → 기존 date_filter 폴백
- [ ] `rm sms.db && python -m app.db.seed` 정상 동작

---

## Step 2: 백엔드 API 스키마 확장

### 수정 파일
- `backend/app/api/templates.py`
- `backend/app/api/template_schedules.py`

### 2-A. Templates API

Pydantic 모델에 추가:
```python
male_buffer: Optional[int] = 0
female_buffer: Optional[int] = 0
gender_ratio_buffers: Optional[str] = None
round_unit: Optional[int] = 0
```

CRUD 함수: 응답 dict + ORM 생성에 4개 필드 반영.

### 2-B. Template Schedules API

Pydantic 모델에 추가:
```python
from typing import Literal

date_target: Optional[Literal['today', 'tomorrow', 'today_checkout', 'tomorrow_checkout']] = None
stay_filter: Optional[Literal['exclude', 'last_only']] = None
```

`_schedule_to_response()` 수정:
```python
"date_target": schedule.date_target,
"stay_filter": schedule.stay_filter,
"once_per_stay": schedule.once_per_stay,  # 기존 누락 수정
```

### Acceptance Criteria
- [ ] API 새 필드 저장/수정/조회 정상
- [ ] `date_target`에 잘못된 값 전송 시 422 에러
- [ ] `stay_filter`에 잘못된 값 전송 시 422 에러
- [ ] `once_per_stay`가 응답에 포함됨 (기존 누락 수정)
- [ ] 기존 API 요청(새 필드 미포함) 시 기본값으로 정상 동작

---

## Step 3: 필터 엔진 확장

### 수정 파일
- `backend/app/scheduler/template_scheduler.py`
- `backend/app/services/room_assignment.py`

### 3-A. `get_targets()` — date_target 적용

date_target이 있으면 우선 사용, 없으면 기존 date_filter 폴백:

```python
date_target = getattr(schedule, 'date_target', None)

if date_target and target_date:
    if date_target.endswith('_checkout'):
        query = query.filter(
            Reservation.check_out_date.isnot(None),
            Reservation.check_out_date == target_date
        )
    else:
        if schedule.target_mode == 'daily':
            query = query.filter(...)  # 기존 범위 비교 그대로
        else:
            query = query.filter(Reservation.check_in_date == target_date)
elif target_date:
    # 기존 date_filter 폴백 (하위 호환)
```

**Safety guard:**
```python
if date_target and date_target.endswith('_checkout'):
    query = query.filter(
        Reservation.check_out_date.isnot(None),
        Reservation.check_out_date <= max_date
    )
else:
    query = query.filter(Reservation.check_in_date <= max_date)
```

**date_target → target_date 변환:**
```python
if date_target:
    if date_target.startswith('tomorrow'):
        target_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        target_date = date.today().strftime('%Y-%m-%d')
```

### 3-B. `get_targets()` — stay_filter (필드 확인만, 서브쿼리 없음)

results 후처리 (once_per_stay 뒤에):

```python
sf = getattr(schedule, 'stay_filter', None)
if sf and results:
    if sf == 'exclude':
        # 연박자 전부 제외 → 단독만
        results = [r for r in results if not r.stay_group_id]
    elif sf == 'last_only':
        # 단독 + 연박 마지막만 (이미 연장한 사람 제외)
        results = [r for r in results if not r.stay_group_id or r.is_last_in_group]
```

**런타임 서브쿼리 0개. is_last_in_group은 연박 감지 시 이미 계산됨.**

### 3-C. `get_schedule_dates()` 수정 (`room_assignment.py`)

```python
def get_schedule_dates(schedule, reservation) -> List[str]:
    date_target = getattr(schedule, 'date_target', None)

    if getattr(schedule, 'target_mode', 'once') == 'daily' and ...:
        return _date_range(...)  # 기존 그대로

    if date_target and date_target.endswith('_checkout'):
        return [reservation.check_out_date or reservation.check_in_date or '']

    return [reservation.check_in_date or '']
```

### 후처리 순서
```
SQL 쿼리 결과 → once_per_stay → stay_filter
```

### Edge Cases
- `date_target=NULL` → 기존 `date_filter` 폴백 (하위 호환)
- `date_target='today_checkout'` + `check_out_date=NULL` → 대상에서 제외
- `stay_filter='last_only'` + `is_last_in_group=NULL` (연박 감지 안 된 예약) → `stay_group_id`도 NULL이므로 자동 포함
- `stay_filter='exclude'` + 단독 예약 → 포함 (정상)

### Acceptance Criteria
- [ ] `date_target='today_checkout'` → check_out_date 기준 필터링
- [ ] `date_target=NULL` → 기존 date_filter로 동작 (하위 호환)
- [ ] `stay_filter='exclude'` → stay_group_id 있는 예약 제외
- [ ] `stay_filter='last_only'` → 단독 + is_last_in_group=true만 포함
- [ ] 런타임 서브쿼리 없음 (필드 확인만)
- [ ] preview API에서도 동일하게 동작

---

## Step 4: 변수 계산 로직 확장

### 수정 파일
- `backend/app/templates/variables.py`
- `backend/app/scheduler/template_scheduler.py` (custom_vars 전달)
- `backend/app/services/sms_sender.py` (custom_vars 전달)
- `backend/app/api/reservations.py` (custom_vars 전달)

### 4-A. AVAILABLE_VARIABLES에 9개 변수 추가

```python
"today_male_count": {"description": "오늘 남성 인원", "example": "13", "category": "party"},
"today_female_count": {"description": "오늘 여성 인원", "example": "12", "category": "party"},
"today_total_count": {"description": "오늘 총 인원", "example": "25", "category": "party"},
"tomorrow_male_count": {"description": "내일 남성 인원", "example": "15", "category": "party"},
"tomorrow_female_count": {"description": "내일 여성 인원", "example": "14", "category": "party"},
"tomorrow_total_count": {"description": "내일 총 인원", "example": "29", "category": "party"},
"yesterday_male_count": {"description": "어제 남성 인원", "example": "10", "category": "party"},
"yesterday_female_count": {"description": "어제 여성 인원", "example": "11", "category": "party"},
"yesterday_total_count": {"description": "어제 총 인원", "example": "21", "category": "party"},
```

### 4-B. 버퍼 적용 헬퍼 함수

```python
def _apply_buffers(male: int, female: int, custom_vars: dict) -> tuple:
    """우선순위: gender_ratio_buffers > male/female_buffer > participant_buffer
    성비 동점(남 == 여) 시 female_high. round_unit은 total에만."""
    # ... (이전 플랜과 동일)
```

### 4-C. calculate_template_variables() — base + prefix 변수

base 변수와 prefix 변수(today/tomorrow/yesterday) 모두 `_apply_buffers` 호출.
**참고**: `get_or_create_snapshot`은 check_in_date 기준 집계 — 주석으로 명시.

### 4-D. custom_vars 전파 — 3곳 모두 동기화

1. `template_scheduler.py` — schedule_custom_vars에 5개 키
2. `sms_sender.py` — SmsBatchSender custom_vars에 5개 키
3. `reservations.py` — 수동 발송 custom_vars에 5개 키

### Acceptance Criteria
- [ ] 9개 프리픽스 변수 정상 치환, 버퍼 동일 적용
- [ ] 버퍼 우선순위: gender_ratio_buffers > male/female_buffer > participant_buffer
- [ ] 성비 동점 → female_high
- [ ] 자동/수동/배치 발송 모두 동일 버퍼 적용

---

## Step 5: 프론트엔드 UI

### 수정 파일
- `frontend/src/pages/Templates.tsx`

### 5-A. TypeScript 인터페이스

```typescript
// Template
male_buffer: number;
female_buffer: number;
gender_ratio_buffers: string | null;
round_unit: number;

// TemplateSchedule
date_target: string | null;
stay_filter: string | null;
```

### 5-B. 템플릿 모달 — "인원 표시 설정"

```
[인원 표시 설정]  ▼
┌─────────────────────────────────────────────────┐
│ 총합 추가  {{participant_count}} + [__N__] 명    │
│ 성별 버퍼  남 +[__N__]  여 +[__M__]              │
│ ☐ 성비 자동 조정                                  │
│   여 >= 남일 때  남+[_] 여+[_]                    │
│   남 > 여일 때   남+[_] 여+[_]                    │
│ 반올림  [__N__] 명 단위 올림 (0=미사용)          │
│ ⓘ 우선순위: 성비 자동 > 성별 버퍼 > 총합 추가    │
└─────────────────────────────────────────────────┘
```

### 5-C. 스케줄 모달 — 기본 필터 + 연박 처리 분리

```
─── 발송 대상 필터 ───
건물         [본관] [별관]                              ← 기존
배정 상태    [객실] [파티만] [미배정]                    ← 기존
컬럼 조건    [파티▾][포함▾][2][추가]                    ← 기존
대상 날짜    [오늘] [내일] [오늘 체크아웃] [내일 체크아웃]  ← 신규 (통합)
요약: "오늘 체크아웃 대상 예약자에게 발송됩니다"

─── 연박 처리 ───
연박자에게    [그대로 발송] [발송 안함] [마지막만 발송]   ← 신규 stay_filter
발송 빈도    [한번만] [매일발송]                         ← 기존 target_mode
```

### 5-D. 스케줄 목록 Badge

```
date_target에 'checkout' 포함  → <Badge color="purple">체크아웃</Badge>
stay_filter == 'exclude'       → <Badge color="warning">연박제외</Badge>
stay_filter == 'last_only'     → <Badge color="info">마지막만</Badge>
target_mode == 'daily'         → <Badge color="info">매일발송</Badge>
```

### Acceptance Criteria
- [ ] 대상 날짜 4개 옵션 정상 작동
- [ ] 연박자에게 3개 옵션 정상 작동
- [ ] 연박 처리가 기본 필터와 별도 섹션으로 분리
- [ ] 기존 모달 기능 깨지지 않음
- [ ] 스케줄 목록 Badge 정상 표시

---

## DB 변경 총 요약

| 테이블 | 컬럼 | 타입 | 기본값 | 용도 |
|--------|------|------|--------|------|
| **Reservation** | `is_last_in_group` | Boolean | NULL | 연박 그룹 마지막 여부 (감지 시 계산) |
| **MessageTemplate** | `male_buffer` | Integer | 0 | 남성 버퍼 |
| | `female_buffer` | Integer | 0 | 여성 버퍼 |
| | `gender_ratio_buffers` | Text | NULL | 성비 조건부 버퍼 (JSON) |
| | `round_unit` | Integer | 0 | 반올림 단위 |
| **TemplateSchedule** | `date_target` | String(30) | NULL | 통합 날짜 필터 |
| | `stay_filter` | String(20) | NULL | 연박 처리 (exclude/last_only) |

**총 7개 컬럼 추가 (3개 테이블). 기존 컬럼 삭제/변경 없음.**

---

## Success Criteria

1. **Backward Compatibility**: date_target=NULL → 기존 date_filter 폴백
2. **날짜 통합**: 4개 옵션으로 체크인/체크아웃 × 오늘/내일 커버
3. **연박 통합**: stay_filter 1개로 연박자·연장자 처리 (서브쿼리 없음)
4. **is_last_in_group**: 연박 감지 시 자동 계산, 멱등
5. **무효 조합 0**: 12조합 전부 유효
6. **버퍼**: gender_ratio_buffers > male/female_buffer > participant_buffer
7. **프리픽스**: 9개 변수 버퍼 포함 정상 치환
8. **UI**: 기본 필터 / 연박 처리 2단 분리 구조
