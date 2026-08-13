# Stay / StayChain — 날짜 개념 통일 설계

> 작성 2026-08-06 · 상태: **설계 (구현 전)**
> 발단: ⑧ `core/calendar` 단위 리뷰 · 사용자 지시 (Q27)
> 선행: [`03-아키텍처-재설계.md`](./03-아키텍처-재설계.md) P5 코어 승격

---

## 0. 한 줄 요약

> **이 시스템이 실제로 쓰는 것은 "밤(night)"인데, 저장은 "사건 날짜(체크인/체크아웃)"로 되어 있습니다.**
> 그래서 쓸 때마다 변환해야 하고, **변환 규칙이 54개 함수에 흩어졌습니다.**
> DB는 그대로 두고, **코드가 만지는 것만 `Stay`로 바꿉니다.**

---

## 1. 왜 필요한가 — 전수조사 근거

### 1-1. 체크아웃 날짜를 "타겟"으로 쓰는 로직은 **0곳**

`check_out_date` 조건 47곳 전수 분류:

| 쓰임새 | 곳 | 실제로 묻는 것 |
|--------|---:|----------------|
| 경계 계산 (`> d`, `>= d`) | 20 | "그날 **밤**에 있나" |
| 밤 목록 (`- timedelta(1)`) | 26 | "마지막 **밤**은?" |
| 당일1박 판정 (`== check_in`) | 3 | "밤이 1개인가" |
| 연박 이어붙이기 (`A.co == B.ci`) | 5 | "A의 다음 밤이 B의 첫 밤인가" |
| 분할 형제 식별 (`co == co`) | 1 | 동일성 매칭 (날짜 의미 아님) |
| 🔴 **체크아웃날 자체를 타겟** | **0** | — |

**증거 ① 체크아웃 타겟 기능은 이미 폐기됨**

```python
# db/models.py:376
date_target = 'today' | 'tomorrow' | 'today_checkout' | 'tomorrow_checkout'
#                                     ↑ 값은 남아 있으나
# schedule_utils.py:86
# Legacy *_checkout or other unknown: log and treat as today
diag("schedule.date_target.legacy_value", level="critical", ...)
return today_kst()
```

**증거 ② 체크아웃이 의미 있는 유일한 도메인(청소)도 체크아웃을 안 씀**

```python
# api/cleancrew.py:8 — "오늘 체크아웃 안 하는 방" 판정
같은 (reservation_id, room_id) 의 RoomAssignment 가 어제와 오늘 모두 존재
```

→ **시스템은 이미 "밤" 기반으로 옮겨왔습니다. 개념이 코드에 명시되지 않았을 뿐입니다.**

### 1-2. 복잡도의 정체

밤을 구하려면 매번 6가지를 동시에 처리해야 합니다:

```
① co 가 NULL 인가?     → 당일 1박
② co 가 '' 인가?        → 당일 1박 (SQL 에선 다르게 동작 🔴 F-4)
③ co == ci 인가?       → 당일 1박
④ co < ci 인가?         → 손상 데이터 (현행 1박 취급)
⑤ 연박 그룹인가?        → 본인 co? 그룹 MAX co? 🔴 F-1
⑥ 마지막 밤 = co - 1    → 26곳에 흩어짐
```

**기능 하나 추가할 때마다 이 6개를 다시 생각해야 하고, 하나라도 빠뜨리면 조용히 틀립니다.**
F-1 · F-2 · F-4 가 정확히 그 결과입니다.

### 1-3. 영향 범위 (실측)

```
check_in_date / check_out_date 를 만지는 함수 : 54개
파일                                          : 24개
```

---

## 2. 개념 — `Stay` 와 `StayChain`

```
Stay        한 예약의 밤들                    (예약 1개)
StayChain   이어붙인 예약들의 밤들             (예약 N개 = 연박 그룹)
```

```
예약 A  4/10 ~ 4/11    Stay(nights=[4/10])
예약 B  4/11 ~ 4/13    Stay(nights=[4/11, 4/12])
                        └─ A.last + 1 == B.first  →  이어짐
StayChain(nights=[4/10, 4/11, 4/12])   ← 손님이 실제로 묵는 전체
```

### 이 개념이 5종을 하나로 통일합니다

| 예약 종류 | 지금 | `Stay` 로 |
|-----------|------|-----------|
| 액티비티 | `has_stay=False` 특수 처리 | 밤 **0개** |
| 파티만 | co 가 NULL/== ci 특수 처리 | 밤 **1개** |
| 당일 예약 | 〃 | 밤 **1개** |
| 일반 1박 | 정상 경로 | 밤 **1개** |
| 연박 3박 | 정상 경로 | 밤 **3개** |
| 연박 그룹 | `stay_group_id` + `is_last_in_group` | `StayChain` 밤 **N개** |

**5종의 특수 케이스가 "개수만 다른 같은 것"이 됩니다.**

> `section_registry.has_stay` 플래그가 이미 이 개념을 절반 표현하고 있었습니다 — *"액티비티는 밤이 없다"*.

---

## 3. 인터페이스

```python
# core/calendar/stay.py
@dataclass(frozen=True)
class Stay:
    nights: tuple[str, ...]          # 불변. 이것이 진실

    @classmethod
    def of(cls, check_in, check_out) -> "Stay":
        """⚠️ NULL · '' · co==ci · co<ci · 파싱실패를 여기서만 처리."""

    def __contains__(self, date: str) -> bool     # d in stay
    def __len__(self) -> int                       # 박 수
    @property
    def first(self) -> str                         # 첫 밤
    @property
    def last(self) -> str                          # 마지막 밤 (당일가드 자동)
    @property
    def is_empty(self) -> bool                     # 액티비티

@dataclass(frozen=True)
class StayChain:
    stays: tuple[Stay, ...]                        # 순서 보장

    @classmethod
    def of(cls, reservations) -> "StayChain"
    # 동일 인터페이스: __contains__ · __len__ · first · last
    @property
    def nights(self) -> tuple[str, ...]            # 전체 합집합
```

### 핵심 설계 결정

| 결정 | 이유 |
|------|------|
| **불변(frozen)** | 밤 목록이 중간에 바뀌면 추적 불가. 변경은 새 `Stay` 생성 |
| **`nights` 가 진실** | `ci`/`co` 는 입력일 뿐. 계산 결과를 캐시하지 않고 밤 자체를 들고 다님 |
| **`Stay` 와 `StayChain` 이 같은 인터페이스** | 호출처가 "한 예약이냐 그룹이냐"를 몰라도 됨 |
| **DB 스키마 무변경** | `ci`/`co` 컬럼 그대로. `Stay.of()` 가 경계에서 한 번 변환 |
| **SQL 짝 유지** | `stay_coverage_filter(d)` = `d in stay` 의 SQL 판. **둘은 짝**임을 명시 |

---

## 4. 무엇이 바뀌나 — Before / After

### ① 마지막 밤

```python
# BEFORE — room_upgrade_common.last_night_of_stay (당일가드 없음 🔴 F-2)
last = datetime.strptime(res.check_out_date, "%Y-%m-%d") - timedelta(days=1)
# co == ci 이면 → 체크인 전날 → 투숙 안 하는 날짜 → 조용히 미발송

# AFTER
stay.last          # nights 가 비어있을 수 없으므로 항상 실제 투숙일
```

> **F-2 가 구조적으로 불가능해집니다.** 가드를 "잊을" 자리가 없습니다.

### ② 그날 묵고 있나

```python
# BEFORE — party3_mms 인라인 (SQL 판과 두 벌 🔴 B-1)
check_in == date or (check_out and check_in <= date < check_out)

# AFTER
date in stay                          # 파이썬
stay_coverage_filter(date)            # SQL — 짝
```

### ③ 당일 1박 / 박 수

```python
# BEFORE
not check_out or check_out == check_in        # is_single_day_stay
max(1, (co - ci).days)                        # stay_nights

# AFTER
len(stay) == 1
len(stay)
```

### ④ 연박 이어붙이기

```python
# BEFORE — consecutive_stay
if prev.check_out_date and prev.check_out_date == curr.check_in_date:

# AFTER
if prev.last + 1day == curr.first:            # StayChain.can_extend(prev, curr)
```

### ⑤ 🔴 F-1 — 그룹의 마지막 밤 (이게 `StayChain` 이 필요한 이유)

```python
# BEFORE — 두 곳이 다름
# 칩 생성  (schedule_utils:30)     : 본인의 check_out - 1
# 발송 필터 (template_scheduler:854): 그룹 MAX check_out - 1
#   → 정상일 땐 같고, 어긋나면 칩은 있는데 발송이 안 됨 (조용히)

# AFTER — 한 곳
chain.last                            # 정의가 하나뿐이라 갈라질 수 없음
```

---

## 5. 함수별 처리 — 전수 (54개)

### 🗑 삭제 — `Stay` 안으로 흡수 (8개)

| 함수 | 위치 | 대체 |
|------|------|------|
| `is_single_day_stay` | `stay_logic.py` | `len(stay) == 1` |
| `stay_nights` | `stay_logic.py` | `len(stay)` |
| `date_range` | `schedule_utils.py` | `stay.nights` |
| `last_night_of_stay` | `room_upgrade_common.py` | `stay.last` (F-2 해소) |
| `_calculate_stay_nights` | `templates/variables.py` | `len(stay)` |
| `compute_is_long_stay` | `consecutive_stay.py` | `len(chain) > 1` |
| `_filter_last_day` | `template_scheduler.py` | `chain.last == target_date` (F-1 해소) |
| party3 인라인 투숙 판정 | `party3_mms.py` | `date in stay` (B-1 해소) |

> ⚠️ `date_range` 는 "순환 때문에 물리적으로 잔류"라고 주석까지 달린 함수입니다. `Stay` 도입 = 그 제약 소멸.

### 🔄 변경 — `Stay`/`StayChain` 을 쓰도록 (14개)

| 함수 | 위치 | 변경 내용 |
|------|------|-----------|
| `get_schedule_dates` | `schedule_utils.py` | 🔴 **가장 큰 변경.** last_night/first_night/기본 3분기가 `chain.last`/`chain.first`/`stay.nights` 로 |
| `stay_coverage_filter` | `filters.py` | 내용 무변경 — **`d in stay` 의 SQL 짝**임을 docstring 에 명시 |
| `detect_and_link_consecutive_stays` | `consecutive_stay.py` | `StayChain.can_extend` 사용 |
| `_validate_link_inputs` | `consecutive_stay.py` | 〃 |
| `_assign_all_rooms` | `room_auto_assign.py` | co 8회 → `stay.nights` |
| `_get_unassigned_reservations` | `room_auto_assign.py` | `d in stay` |
| `reconcile_stale_chips` | `room_auto_assign.py` | 〃 |
| `_reconcile_dates` | `room_assignment.py` | `stay.nights` 로 배정 범위 산출 |
| `_compute_bed_order` | `room_assignment.py` | `- timedelta(1)` 제거 |
| `_shift_daily_records` | `room_assignment.py` | `stay.nights` 평행이동 |
| `_condition_column_match` | `filters.py` | ci/co 각 6회 → `Stay` 경유 |
| `get_sales_report` | `api/sales_report.py` | `d in stay` |
| `search_reservations` | `api/event_sms.py` | 〃 |
| `_get_candidate_reservations` | `chip_reconciler.py` | 〃 |

### ✅ 유지 — `Stay` 와 무관 (32개)

**이유별로 묶으면:**

| 이유 | 함수 | 왜 유지 |
|------|------|---------|
| **입력 검증** | `_validate_dates` · `_check_date_order` (`reservations_shared`) | `Stay` 를 만들기 **전** 단계. 형식·순서 검증 |
| **저장/변경** | `_create_reservation` · `_update_reservation` (`naver_sync`) · `apply_changes` (`mutator`) | `ci`/`co` **컬럼 자체**를 쓰는 게 맞음 |
| **동일성 매칭** | `alert_unsplit_multi` · `find_confirmed_siblings` (`split_group_guard`) | 날짜를 **식별 키**로 씀 (밤 개념 아님) |
| **API 입출력** | `create/update/get/delete_reservation` (`api/reservations`) · `_to_response` | 화면과 주고받는 건 `ci`/`co`. 경계에서 변환 |
| **연장/축소** | `extend_stay` · `_do_reduce_extension` (`reservations_stay`) | `co` 를 **직접 이동**시키는 게 목적 |
| **템플릿 변수** | `send_single_sms` · `calculate_template_variables` | `{{체크인}}` 등 표시용 |
| 기타 | 나머지 | 날짜를 스쳐 지나감 |

> **32개가 그대로라는 게 중요합니다.** `Stay` 는 시스템을 뒤집는 게 아니라
> **"밤을 계산하는 22곳"만** 걷어내는 작업입니다.

### ➕ 신규 (2개 파일)

```
core/calendar/stay.py         Stay · StayChain
core/calendar/coverage.py     stay_coverage_filter (filters.py 에서 분리) — Stay 의 SQL 짝
```

---

## 6. 무엇이 해결되나

| # | 문제 | 해결 방식 |
|---|------|-----------|
| **F-1** | 마지막밤 기준 두 곳이 다름 (칩=본인 co / 발송=그룹 MAX) | `chain.last` **정의가 하나** → 갈라질 수 없음 |
| **F-2** | `last_night_of_stay` 당일예약 가드 누락 | `stay.last` 는 항상 실제 투숙일 → **구조적으로 불가능** |
| **F-4** | `''` vs `NULL` 이 SQL/파이썬에서 갈라짐 | `Stay.of()` **한 곳에서만** 처리 |
| **B-1** | 파티MMS 투숙 판정 SQL판·파이썬판 두 벌 | `d in stay` ↔ `stay_coverage_filter(d)` **짝으로 명시** |
| **D-3** | `date_range` 가 순환 때문에 "물리적 잔류" | 코어 이동으로 제약 소멸 |
| — | 밤 계산 로직 **22곳 분산** | **1곳** |

---

## 7. 무엇이 해결되지 **않나** (정직하게)

| # | 남는 문제 | 이유 |
|---|-----------|------|
| 1 | **`''` 가 DB에 저장되는 것 자체** | 뿌리는 `real/reservation._format_date` 가 파싱 실패 시 `''` 반환. **입구에서 막아야 함** — `Stay` 는 읽기 쪽만 방어 |
| 2 | **`co < ci` 손상 데이터** | `Stay.of()` 가 현행대로 1박 취급(no-op 보존). 정책 변경은 별도 결정 (LB-08) |
| 3 | **F-1 의 "정답"** | `chain.last` 로 통일되지만 **"그룹 MAX 가 맞다"는 판단은 사람이** 해야 함 |
| 4 | **`stay_group_id` / `is_last_in_group` 컬럼** | `StayChain` 이 도입돼도 DB 컬럼은 유지 (그룹 식별용). 계산만 `StayChain` 이 함 |
| 5 | **프론트엔드 `stayLogic.ts` 미러** | 같은 규칙이 프론트에도 있음. 이번 범위 밖 (백엔드 우선) |

---

## 8. 단계

> ⚠️ **P5 순수 이동에 섞지 마세요.** 22곳 치환은 no-op 이 아닙니다.

| # | 단계 | 내용 | 위험 |
|---|------|------|------|
| **S1** | 특성화 테스트 | 22곳의 **현재 동작**을 테스트로 고정 (`''`·`co==ci`·`co<ci`·그룹 포함) | 🟨 |
| **S2** | `Stay` / `StayChain` 신설 | 기존 코드 무변경. 새 파일만 추가 | 🟨 없음 |
| **S3** | 등가 증명 | 기존 8함수 vs `Stay` 를 **같은 입력에 넣어 출력 대조** | 🟨 |
| ~~S4~~ | ✅ **F-1 결정 완료** | **(가) 그룹 MAX 확정** (2026-08-06, Q30) → §11 | — |
| **S5** | 치환 (읽기) | `d in stay` · `len(stay)` 계열 14곳 | 🟧 |
| **S6** | 치환 (쓰기) | `stay.nights` 로 배정/칩 범위 산출 | 🟥 |
| **S7** | 8함수 삭제 | 참조 0 확인 후 | 🟨 |
| **S8** | F-1·F-2 수정 | 통일된 자리에서 한 번에 | 🟧 |

**선행**: P5 코어 승격 (`stay_coverage_filter` 가 `core/calendar` 에 있어야 `Stay` 가 살 자리가 생김)

---

## 9. 위험

| # | 위험 | 대비 |
|---|------|------|
| **W1** | 🟥 22곳 치환은 **no-op 이 아님** — 미묘한 동작 변화 가능 | S1 특성화 테스트 + S3 등가 증명 **먼저** |
| **W2** | 🟥 `Stay.of()` 가 현행 6가지 처리를 **하나라도 다르게** 하면 전역 영향 | S3 에서 8함수와 1:1 대조 |
| **W3** | 🟧 `StayChain` 생성이 **N+1 쿼리**를 유발할 수 있음 | 배치 로딩 설계 필요 (`_filter_last_day` 가 이미 그룹 MAX 를 배치 조회 중 — 그 패턴 계승) |
| **W4** | 🟧 diag 이벤트 이름·순서 동결 (R6) | 치환은 계산만 바꾸고 diag 호출은 유지 |
| **W5** | 🟨 프론트 미러와 규칙 어긋남 | 백엔드 확정 후 프론트 동기 (별도) |

---

## 10. 결정 기록

| # | 질문 | 결정 |
|---|------|------|
| **Q27** | 날짜 개념을 통일할까? | **`Stay` / `StayChain` 도입** (사용자 지시) |
| **Q28** | DB 스키마를 바꿀까? | **아니오** — `ci`/`co` 컬럼 유지, 경계에서 변환 |
| **Q29** | 시점? | **P5 코어 승격 직후 별도 단계** (P5 에 섞지 않음) |
| **Q30** | F-1 정답 (그룹 MAX vs 본인 체크아웃)? | ✅ **(가) 그룹 MAX 확정** — 아래 §11 |

---

## 11. F-1 결정 — **(가) 그룹 MAX** (2026-08-06 확정)

### 두 안의 실제 차이

```
(가) 그룹 MAX      그룹 전체를 조회해 MAX(check_out_date) 를 매번 계산 → 지금 DB 가 진실
(나) 본인 체크아웃  is_last_in_group=True 인 예약의 check_out_date 사용 → 저장된 플래그를 믿음
```

### 🔴 결정적 근거 — `is_last_in_group` 은 **낡을 수 있습니다**

`is_last_in_group` 은 계산 결과를 박아둔 **저장 컬럼**입니다 (`db/models.py:89`).
그런데 **날짜가 바뀌어도 자동 갱신되지 않습니다.**

`on_dates_changed` 가 하는 일 (`reservation_lifecycle.py:25`):

```
① shift_daily_records    날짜별 기록 평행이동
② reconcile_dates        배정표 정리
③ reconcile_all_chips    칩 5종 재계산
                         ← detect_and_link_consecutive_stays 가 없음 🔴
```

**재계산 시점 (실측):**

| 시점 | 경로 |
|------|------|
| 하루 4회 (09·10·11·12시) | `scheduler/jobs.py:159` `detect_consecutive_stays_job` |
| 네이버 동기화 직후 | `sync_naver_to_db` Phase 4 |
| 연박 연장 버튼 | `api/reservations_stay.py:67` — **이 경로만 직접 호출** |

→ **직원이 예약 날짜를 수정하면, 다음 감지(최대 몇 시간 뒤)까지 플래그가 낡은 상태로 남습니다.**

### 낡았을 때 무슨 일이 벌어지나

| 상황 | (나) 본인 체크아웃 | (가) 그룹 MAX |
|------|-------------------|---------------|
| 플래그 대상보다 **늦은 체크아웃**이 생김 | 🔴 이른 날짜에 발송 | ✅ 정상 |
| 플래그가 **아무에게도 없음** | 🔴 **칩이 아예 안 생김** | ✅ 정상 |
| 플래그가 **여러 명**에게 있음 | 🔴 칩 여러 개 | ✅ 1개 |
| 멤버 중 `''` 체크아웃 | ✅ 영향 없음 | 🟡 MAX 가 `''` 를 집을 수 있음 (F-4) |

### 지금 코드가 둘 다 쓰고 있는 것이 F-1 의 정체

```
칩 생성   (schedule_utils:30)      →  (나) 본인 체크아웃
발송 필터 (template_scheduler:854) →  (가) 그룹 MAX

플래그가 낡으면:  칩은 4/12 에 생기고 · 발송 필터는 4/15 를 찾음
        ↓
💥 칩은 있는데 발송 안 됨. 칩이 남아 있어 화면엔 "발송 대기중"으로 보임
```

### (가)를 고른 이유 3가지

| # | 이유 |
|---|------|
| **1** | **(나)는 파생 데이터를 믿는 구조.** 저장된 파생 데이터는 반드시 낡습니다 — 이 저장소에서 반복 확인된 패턴 |
| **2** | **(가)는 자기교정.** 플래그가 틀려도 결과가 맞습니다 |
| **3** | **최종 관문에 맞춤.** `_filter_last_day`(발송 필터)가 이미 (가)를 쓰고, 그게 실제로 손님에게 문자가 나가는 마지막 지점입니다 |

### 부수 효과

`is_last_in_group` 컬럼을 **삭제하는 게 아닙니다.** 다른 용도(화면 표시 등)로는 계속 쓰입니다.
바뀌는 것은 **문자 발송이 더 이상 이 플래그에 의존하지 않는다**는 것입니다.

> 🟡 **별도 관찰**: `on_dates_changed` 가 연박 재계산을 안 부르는 것 자체는 남는 문제입니다.
> (가) 채택으로 **문자 발송 영향은 사라지지만**, 플래그를 쓰는 다른 곳(화면 표시 등)은 여전히
> 최대 몇 시간 낡은 값을 봅니다. → `StayChain` 도입 후 재검토 (플래그 자체를 계산으로 대체 가능한지).
