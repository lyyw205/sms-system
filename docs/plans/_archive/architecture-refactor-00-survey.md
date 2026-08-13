# 아키텍처 전면 리팩토링 — 0단계: 현황 실측 & 분해축 조사

> 상태: **조사 (설계 전)** · 작성 2026-08-06
> 목적: "코어 + 모듈" 아키텍처로 재편하기 위해, **먼저 현재 무엇이 있고 무엇이 예외인지** 전수 확인한다.
> 원칙: 이 문서는 **판단하지 않는다.** 측정값과 선택지만 적는다. 결정은 사람이 §5에서 한다.

---

## 0. 측정 기준

| 항목 | 값 |
|------|-----|
| 백엔드 `app/` | 85 파일 · **21,168 LOC** · 함수 정의 438개 |
| 백엔드 `tests/` | 67 파일 · 10,786 LOC |
| 프론트 `src/` | **21,812 LOC** |
| 실제 top-level import 순환 | **0건** |
| 함수 내부 지연 import (순환 회피 흔적) | **240건 / 38파일** ← 진짜 순환은 여기 숨어있음 |

---

## 1. ⚠️ 먼저: CLAUDE.md 와 코드가 어긋난 부분

리팩토링 계획을 CLAUDE.md 기준으로 세우면 **없는 것을 설계하게 된다.** 실측 결과:

| CLAUDE.md 서술 | 실제 |
|----------------|------|
| 핵심 패턴 #1 **"Provider Factory + Hot-Swap (DEMO_MODE로 Mock/Real 전환)"** | ❌ **죽음.** `mock/` 디렉토리 없음. `factory.py` docstring = "always Real (no mock)". `DEMO_MODE`는 Sentry/Swagger/CORS/시크릿 검증에만 남음 |
| `providers/`: base + mock/sms + mock/llm + real/llm | ❌ `providers/base.py` 하나. `real/`은 sms·reservation 2개. **LLM 전체 소멸** |
| `router/message_router.py` 자동응답 파이프라인 (DB→YAML→LLM→검토큐) | ❌ **`router/` 디렉토리 자체가 없음** |
| 모델 `Message`, `Rule`, `GenderStat`, `CampaignLog` | ❌ models.py에 없음 |
| 라우터 `messages`, `webhooks`, `auto_response`, `rules`, `documents`, `reservations_sync` | ❌ 없음 |
| "19개 라우터" | 실제 main.py `include_router` **24회** |
| `services/sms_tracking.py` (칩 생성/조회) | ❌ **`chip_store.py`로 대체됨** (536 LOC) |
| 페이지 12개 | 실제 더 많음 (SalesReport, EventSms, Quick 등) |

**CLAUDE.md에 아예 없는 실존 모듈** (= 문서화 안 된 채 자라난 영역):
`services/split_group_guard.py`(613) · `services/chip_store.py`(536) · `services/section_registry.py` · `services/party_type.py` · `services/stay_logic.py` · `services/dorm_gender.py` ·
`api/sales_report.py`(307) · `api/event_sms.py` · `api/scheduler.py` · `api/cleancrew.py` · `api/daily_host.py` · `api/daily_review.py` · `api/party_hosts.py` · `api/onsite_female_invite.py`

> **결론**: 리팩토링 1번 산출물은 **CLAUDE.md 재작성**이어야 한다. 현재 문서는 신뢰할 수 없다.

---

## 2. 현재 구조 — 실측 의존성 지형

### 2-1. Fan-in (많이 의존받는 = 사실상의 커널)

```
55  db.models          ← 모든 것이 여기 의존. 단일 거대 스키마 파일(603 LOC, 24 모델)
45  diag_logger        ← 횡단 관심사. 사실상 코어
24  config
22  auth.dependencies
21  api.deps
15  db.tenant_context
12  services.chip_store       ← ✅ 성공적으로 통합된 게이트웨이
11  services.activity_logger
 9  services.filters / section_registry
 8  services.reconcile
```

### 2-2. Fan-out (많이 의존하는 = 오케스트레이터 또는 God-module)

```
20  api.reservations             (669 LOC)
17  api.rooms                    (956 LOC)
17  services.naver_sync          (1,008 LOC)  ← 서비스인데 fan-out 3위 = 계층 위반
15  scheduler.template_scheduler (867 LOC)
13  api.reservations_stay / services.room_assignment(1,110) / room_auto_assign(666)
```

### 2-3. 🔴 숨은 순환 — 지연 import 240건

top-level 순환은 0건이지만, **`# 순환 import 회피용 지연 import` 주석이 달린 함수 내부 import가 240건**이다. 실제 논리 순환:

```
room_assignment ──(:546 지연)──> reconcile ──(:38 지연)──> room_assignment
                                     ├──> surcharge
                                     ├──> party3_mms
                                     ├──> room_upgrade_promise
                                     └──> room_upgrade_review
```

지연 import 최다: `api.reservations`(23) · `naver_sync`(20) · `api.reservations_stay`(19) · `reservation_lifecycle`(19) · `api.rooms`(13) · `room_assignment`(13)

> **이것이 "코어/모듈 분리"가 필요한 가장 강한 물리적 증거.** 240건은 전부 "레이어가 안 맞는데 호출은 해야 해서" 생긴 우회로다.

### 2-4. 거대 함수 (분해 1순위)

| LOC | 위치 | 함수 |
|-----|------|------|
| 420 | `services/naver_sync.py:57` | `sync_naver_to_db` |
| 386 | `db/database.py:112` | `init_db` ← **런타임 자동 마이그레이션이 여기 통째로** |
| 357 | `services/room_assignment.py:214` | `assign_room` |
| 295 | `scheduler/template_scheduler.py:35` | `execute_schedule` |
| 265 | `services/naver_sync.py:739` | `_update_reservation` |
| 250 | `api/reservations.py:254` | `update_reservation` |
| 238 | `api/sales_report.py:69` | `get_sales_report` |
| 221 | `services/sms_sender.py:31` | `send_single_sms` |
| 199 | `services/room_auto_assign.py:293` | `_assign_all_rooms` |
| 195 | `services/consecutive_stay.py:49` | `detect_and_link_consecutive_stays` |

---

## 3. 코어 vs 모듈 — 분해 후보 (초안)

현재 디렉토리(`api/` `services/` `scheduler/`)는 **기술 계층**으로 나뉘어 있고, 도메인 경계가 없다. 실측 의존성을 기준으로 자연스러운 절단면을 뽑으면:

### 🔵 CORE — 도메인 불변식의 소유자 (모듈이 의존, 모듈에 의존 안 함)

| 코어 | 현재 위치 | 책임 | 상태 |
|------|-----------|------|------|
| **C1. Tenant/Identity** | `db/tenant_context`, `auth/*`, `api/deps` | 테넌트 격리, 인증, 스코프 세션 | ✅ 비교적 깨끗 |
| **C2. Reservation Entity** | `db/models.Reservation`, `reservation_mutator` | 예약 필드의 **유일한 쓰기 게이트웨이** + 권한 행렬 | 🟡 우회 24곳 |
| **C3. Stay Calendar** | `stay_logic`, `schedule_utils.date_range`, `consecutive_stay` | 날짜/박/연박그룹 산술의 단일 진실 | 🟡 Phase A만 |
| **C4. Chip Store** | `chip_store` | 칩 CRUD 단일 게이트웨이 | ✅ **성공 사례** (생성 3곳 전부 내부) |
| **C5. Domain Vocabulary** | `section_registry`, `party_type`, `room_grade` | enum-like 도메인 값의 명세서 | ✅ **성공 사례** |
| **C6. Lifecycle Bus** | `reservation_lifecycle`, `reconcile` | 변경 → 후처리 순서 보장 | 🟡 순환의 진원지 |
| **C7. Observability** | `diag_logger`, `activity_logger`, `event_bus` | diag/감사/SSE | ✅ 깨끗 (fan-in 45) |

### 🟢 MODULE — 코어 위에 얹히는 기능 (서로 몰라야 함)

| 모듈 | 현재 파일 | 비고 |
|------|-----------|------|
| **M1. 객실 배정** | `room_assignment`(1110) · `room_auto_assign`(666) · `room_assignment_invariants` · `room_lookup` · `dorm_gender` · `api/rooms`(956) · `api/reservations_room` | 최대 덩어리 |
| **M2. SMS 발송** | `sms_sender` · `real/sms` · `templates/renderer` · `templates/variables` · `api/reservations_sms` | |
| **M3. 스케줄 타겟팅** | `template_scheduler`(867) · `schedule_manager` · `filters`(541) · `api/template_schedules`(654) | **예외 최대 밀집지** |
| **M4. 커스텀 발송 5종** | `custom_schedule_registry` · `surcharge` · `party3_mms` · `room_upgrade_common/promise/review` | 이미 레지스트리 패턴 |
| **M5. 네이버 연동** | `naver_sync`(1008) · `real/reservation` | 유일한 외부 인바운드 |
| **M6. 파티 운영** | `api/party_checkin` · `party_hosts` · `daily_host` · `daily_review` · `onsite_female_invite` · `cleancrew` | 소규모 다수 |
| **M7. 연박/분할 그룹** | `consecutive_stay`(445) · `split_group_guard`(613) | |
| **M8. 리포팅** | `api/sales_report` · `api/dashboard` · `api/activity_logs` | 읽기 전용 |
| **M9. 이벤트 SMS** | `api/event_sms` · `event_sms_hook` | |

### 🔴 즉시 드러나는 계층 위반

1. `naver_sync`(서비스)가 fan-out 17 — API 레이어보다 많이 의존. **M5가 코어를 우회해 다른 모듈을 직접 호출**
2. `room_assignment` ↔ `reconcile` 순환 — **M1이 C6를, C6가 M1을 호출**
3. `db/database.init_db` 386줄 — 스키마 마이그레이션이 부트스트랩에 하드코딩
4. `api/reservations*` 5개 파일이 사실상 하나의 God-router가 쪼개진 것 (`reservations`, `_room`, `_sms`, `_stay`, `_shared`)

---

## 4. 예외 & 변수 전수 리스트 — **리팩토링이 하나도 잃으면 안 되는 것**

### 4-A. 도메인 값 축 (enum-like 문자열)

| 축 | 값 | 정의 위치 | 함정 |
|----|-----|-----------|------|
| `section` | `room` `unassigned` `party` `unstable` `activity` | `section_registry.SECTIONS` | NULL/미지 → `unassigned` 계승. **7개 속성 축**(assignable/lodging_guest/has_stay/draggable/default_party_inherit/naver_inbound/label). ⚠️ **오버레이 5종은 명세서에 없음**: room_id 우선 · unstable_party · party_type 오버레이 · sectionOverrides(FE) · room 카테고리 modifier |
| `party_type` | `1`(1차만) `2`(1+2차) `2차만` NULL/`''`(미참여) + `X`(daily 미참여) | `party_type.py` | ⚠️ **두 집합 병합 금지**: `PARTY_JOINED_TYPES{1,2,2차만}` ⊃ `PARTY3_2CHA_TYPES{2,2차만}`. ⚠️ effective 폴백이 3가지: Python truthy / SQL coalesce / `is not None` — **의도적 차이, 통일 금지** |
| `status` | `PENDING` `CONFIRMED` `CANCELLED` `COMPLETED` | `ReservationStatus` | |
| `booking_source` | `naver` `manual` `phone` | 컬럼 주석만 | 명세 모듈 없음 |
| 칩 `assigned_by` | `auto` `manual` `schedule` `excluded` `failed` | `chip_store.PROTECTED_ASSIGNED_BY=('manual','excluded','failed')` | reconcile이 삭제 못 하는 보호 집합 |
| 배정 `assigned_by` | `auto` `manual` | `RoomAssignment` | **칩의 assigned_by와 값 집합이 다른 동명 컬럼** |
| `room.grade` | 1~5 (도미<더블<트윈<트윈3인<스위트) | `room_grade.py` | `NaverBizItem.grade`와 비교해 업그레이드 판정 |
| `UserRole` | `SUPERADMIN` `ADMIN` `STAFF` | + `api/auth.ROLE_HIERARCHY` | |

### 4-B. 스케줄 타겟팅 축 (M3 — 예외 최대 밀집)

| 축 | 값 | 비고 |
|----|-----|------|
| `schedule_type` | `daily` `weekly` `hourly` `interval` | + `active_start_hour`/`active_end_hour` (hourly/interval 전용) |
| `schedule_category` | `standard` `event` `custom_schedule` | 3종이 **완전히 다른 타겟 선정 함수**를 탐 (`_get_targets_standard` 137줄 / `_get_targets_event`) |
| `custom_type` | `surcharge_standard` `surcharge_double` `party3_today_mms` `room_upgrade_promise` `room_upgrade_review` | `PER_DATE_DEDUP_CUSTOM_TYPES={party3_today_mms}` 만 (예약,날짜) dedup, 나머지는 stay 단위 |
| `target_mode` | NULL(stay-coverage) `first_night` `last_night` | ⚠️ `last_night` 권위가 칩측(OWN checkout) vs 발송측(`func.max`) **불일치** (LB-06/07) |
| `date_target` | `today` `tomorrow` `today_checkout` `tomorrow_checkout` | |
| `stay_filter` | NULL(포함) `exclude`(연박 제외) | v2에선 room 필터 안, v1 레거시는 별도 컬럼 — **dual-parse** |
| `gender_filter` | `male` `female` NULL | |
| `send_condition_*` | `date`(today/tomorrow) · `ratio`(N:1) · `operator`(gte/lte) | 성비 조건 발송 |
| `once_per_stay` | bool | 연박 그룹 내 최초 체크인만 |
| `exclude_sent` | bool | |
| `max_checkin_days` / `hours_since_booking` / `expires_after_days` | int | event 전용 |
| 필터 `type` | v2: `assignment` `column_match` / v1 레거시: `building` `room` `room_assigned` `party_only` `has_unassigned` | **normalize-on-read dual parser** — v1 그대로 DB에 남아있음 |
| `assignment.value` | `room` `party` `unassigned` `unstable` | room만 `buildings[]`·`include_unassigned`·`stay_filter` modifier 보유 |
| `column_match.column` | `party_type` `gender` `naver_room_type` `notes` `customer_name` | `_COLUMN_MATCH_DATE_DEPENDENT={party_type,notes}` 만 날짜 의존 |
| **결합 규칙** | assignment 여러개=**OR** · column_match 여러개=**AND** · 둘 사이=**AND** | |

### 4-C. 보호 플래그 (덮어쓰기 방지) — 8종

| 플래그 | 보호 대상 | 주 사용처 |
|--------|-----------|-----------|
| `check_in_pinned` / `check_out_pinned` | 네이버 sync의 날짜 덮어쓰기 | mutator `_PIN_ATTR_FOR` |
| `manually_edited_fields` (JSON) | 5개 신규 필드 + status | mutator, naver_sync |
| `manually_extended_until` | 수동 연장 | ⚠️ **deprecated 예정, pin과 공존 중** |
| `gender_manual` | 성별 재계산 | naver_sync |
| `stay_group_excluded` | 자동 연박 재묶기 | consecutive_stay |
| `is_split_managed`* | 분할 그룹 | split_group_guard |
| 칩 `assigned_by ∈ PROTECTED` / `sent_at IS NOT NULL` | reconcile 삭제 | chip_store |
| `Room.is_active` / `is_hidden` | 배정 차단 / 카드 미노출(+미래 배정 삭제) | room_auto_assign |

사용 분포: `naver_sync`(23) · `api/reservations`(19) · `mutator`(14) · `split_group_guard`(11) · `consecutive_stay`(7)

### 4-D. 쓰기 권한 행렬 (`FIELD_PERMISSIONS`)

`ChangeSource` = `NAVER` / `MANUAL` / `SYSTEM` × 권한 `guarded` / `always` / `never` × **17개 필드**.
특이 케이스:
- `section`: NAVER=**never** (네이버는 section 못 바꿈)
- `naver_room_type`, `booking_options`: MANUAL=**never** (직원이 못 바꿈)
- `status`: MANUAL=always지만 auto-mark로 핀이 박혀 **네이버 부활 차단** + `is_manual_cancel=True`

### 4-E. 날짜/시간 예외

| 예외 | 내용 |
|------|------|
| `check_out_date` 3중 표현 | NULL / `''` / `co==ci` — 전부 "당일 1박". `''`은 Python truthy엔 안전, **SQL `is_(None)`·`func.max`에선 갈라짐** |
| `''`의 출처 | `real/reservation.py:364 _format_date` (LB-01, 미수정) |
| 반열림 규약 | 박 집합 = `[check_in, check_out)` — **체크아웃일은 박이 아님** |
| `stay_nights` floor | `max(1, diff)` — **유일한 금액 곱셈** (`variables.py:304`), co<ci를 조용히 1박 청구 (LB-08) |
| long-stay 임계 | `(co-ci).days > 1` — single-vs-multi와 **다른 임계** |
| 비-zero-pad 날짜 | `'2026-1-9'` → 사전식 SQL 비교 전반 오정렬 |
| 타임존 | KST 고정, `today_kst()` / `today_kst_date()` (17곳 치환 완료) |
| cascade clamp | 연박자 + apply_subsequent + 과거 드롭일 때만 today로 clamp (INV-4) |

### 4-F. 런타임 불변식 (INV-1~8, `docs/diag-golden/invariants.md`)

1. request enter/exit 짝 · 2. assign_room enter/exit 짝 · 3. `schedule.execute.exit`의 `outcome` 6값 필수 ·
4. cascade clamp 가드 3조건 · 5. **금지 이벤트 5종 재출현 없음**(회귀 탐지) · 6. `/health` 노이즈 없음 ·
7. `naver_sync.exit`의 `synced == added+updated` · 8. PII 마스킹

> 리팩토링 중 diag 이벤트 이름이 바뀌면 **정답지(`docs/diag-golden/actions/*.yaml`) 전체가 무효화**된다. 이게 이 프로젝트의 유일한 회귀 안전망이므로 다루는 방식을 먼저 정해야 한다.

---

## 5. 중복 / 분산 후보

### 5-1. 동명 함수 (실측)

| 함수명 | 위치 | 성격 |
|--------|------|------|
| `ensure_chip` / `remove_chip` | `chip_store` ↔ `room_upgrade_common` | 🔴 래퍼인지 중복인지 확인 필요 |
| `decide_chip` | `room_upgrade_promise` ↔ `room_upgrade_review` | 🟡 의도적 분리(약속/객후) |
| `_find_schedule` | `party3_mms` ↔ `surcharge` | 🔴 통합 후보 |
| `preview_targets` | `api/template_schedules` ↔ `template_scheduler` | 🔴 API가 로직 재구현 의심 |
| `get_custom_types` | `api/template_schedules` ↔ `custom_schedule_registry` | 🟡 얇은 위임 |
| `assign_room` | `api/reservations_room` ↔ `services/room_assignment` | 🟡 API 111줄 / 서비스 357줄 — API가 두꺼움 |
| `get_template` | `api/templates` ↔ `templates/renderer` | 🔴 |

### 5-2. 게이트웨이 우회 (통합 미완)

| 게이트웨이 | 우회 건수 | 우회처 |
|-----------|----------|--------|
| `ReservationMutator` | **최소 24곳** | `consecutive_stay`(11) · `naver_sync`(9) · `templates/variables`(2) · `room_assignment`(1) · `api/reservations_room`(1) |
| `chip_store` (생성) | **0곳** ✅ | 완전 통합 |
| `chip_store` (읽기/쿼리) | **14파일**이 `ReservationSmsAssignment` 직접 참조 | 쓰기는 막았으나 읽기는 산개 |

### 5-3. 인라인 복제 (stay-semantics 설계안에서 이미 식별)

- Python stay-coverage 인라인 복제: `sales_report:135` · `party3_mms:168` · `room_auto_assign:249`
- SQL coverage 인라인: `reservations:70/84` · `rooms:401` · `naver_sync:495` · `room_auto_assign:519` · `sales_report:112` · `consecutive_stay:84/98`
- 인라인 박-범위 루프: `reservations_stay:359-364`, `:186`
- FE 중복: `GuestRow:118` ↔ `MobileGuestRow:91` (lockstep 수정 필요)

---

## 6. 이 프로젝트가 이미 찾아낸 "정답 패턴"

리팩토링을 **새로 발명하지 말고 이 3개를 확산**하는 게 맞는지부터 결정해야 한다:

| 패턴 | 성공 사례 | 형태 |
|------|-----------|------|
| **명세서 모듈** | `section_registry` · `party_type` · `stay_logic` | 흩어진 하드코딩 → frozen dataclass/frozenset 단일 테이블 + "무엇을 담지 않는가" 명시 |
| **단일 게이트웨이** | `chip_store` (✅ 완전) · `reservation_mutator` (🟡 24곳 우회) | 모든 쓰기가 한 함수를 통과 + 권한 행렬 |
| **레지스트리** | `custom_schedule_registry` | 신규 타입 = 테이블 한 줄 추가 |
| **정답지 검증** | `diag-golden` | diag 이벤트 시퀀스를 YAML로 고정 |

---

## 7. 사람이 결정해야 할 것 — 다음 단계 입력

리팩토링 설계에 들어가기 전에 아래가 확정돼야 한다. (구체화는 §7 순서대로)

### Q1. 분해축을 무엇으로 잡을 것인가
- **(a) 도메인 모듈형** — `reservation/` `room/` `sms/` `party/` `naver/` 각각 안에 api+service+model
- **(b) 코어/모듈 2층** — `core/`(§3 C1~C7) + `modules/`(M1~M9), 모듈은 코어만 의존
- **(c) 현행 계층 유지 + 순환만 제거** — 최소 침습

### Q2. 240건 지연 import 를 어떻게 없앨 것인가
- 이벤트 버스로 역방향 호출 차단 / 인터페이스(Protocol) 주입 / 호출 방향 자체를 뒤집기

### Q3. diag 이벤트 이름을 리팩토링 중 보존할 것인가
- 보존 → 정답지 유효, 대신 새 구조에서 이름이 어색해짐
- 재작성 → 정답지 전면 재생성 필요 (안전망 일시 상실)

### Q4. `db/models.py` 603줄 24모델을 도메인별로 쪼갤 것인가
- fan-in 55의 최상위 의존점 — 쪼개면 전 파일 import 변경

### Q5. `api/reservations*` 5분할을 유지/재편할 것인가

### Q6. 프론트(21.8k LOC)를 이번 범위에 포함할 것인가
- `Templates.tsx` 2,526줄 · `RoomSettings.tsx` 1,473줄 · `RoomAssignment.tsx` 1,354줄
- 백엔드 도메인 경계가 바뀌면 FE 미러(`stayLogic.ts`, sectionSpec)도 따라가야 함

### Q7. CLAUDE.md 재작성을 선행할 것인가 (§1 드리프트)

---

## 8. 다음 산출물 (예정)

- `architecture-refactor-01-target.md` — Q1 결정 후 목표 구조 확정
- `architecture-refactor-02-invariant-freeze.md` — §4 예외 전체를 특성화 테스트로 핀
- `architecture-refactor-03-steps.md` — no-op 단계 분해 (기존 mutator/lifecycle plan 방식 계승)
