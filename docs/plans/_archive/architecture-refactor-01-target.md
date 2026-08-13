# 아키텍처 전면 리팩토링 — 1단계: 목표 구조 & 위반 전수 등록

> 상태: **설계 (구현 전)** · 작성 2026-08-06 · 선행: [`architecture-refactor-00-survey.md`](./architecture-refactor-00-survey.md)
> 확정된 결정 (2026-08-06):
> - **분해축 = 코어/모듈 2층** — 모듈은 코어만 의존, 모듈끼리 직접 호출 금지
> - **diag 이벤트명 전면 보존** — 파일이 이동해도 `diag()` 문자열 동결 → `diag-golden` 정답지 무수정, 매 단계 `diff_trace.py` 로 no-op 증명
> - **범위 = 백엔드 우선** — 프론트는 API 계약 변경분 + 미러(`stayLogic.ts`/sectionSpec) 동기만

---

## 1. 의존 규칙 (이 리팩토링의 헌법)

```
      main.py / bootstrap        ← 유일하게 전부를 알아도 되는 곳 (composition root)
              │
        ┌─────┴─────┐
        ▼           ▼
    modules/*    core/*
        │           ▲
        └───────────┘   모듈 → 코어 (허용)
                        코어 → 모듈 (금지)
                        모듈 → 모듈 (금지)
```

| # | 규칙 | 위반 시 |
|---|------|---------|
| R1 | 모듈은 **코어만** import 한다 | CI lint 실패 |
| R2 | 코어는 **모듈을 절대 import 하지 않는다** (지연 import 포함) | CI lint 실패 |
| R3 | 모듈 간 협력이 필요하면 **코어의 레지스트리/이벤트**를 경유한다 | — |
| R4 | `bootstrap/` (composition root) 만 예외 — 모든 모듈을 알고 배선한다 | — |
| R5 | 함수 내부 지연 import 금지 (R1~R3을 지키면 필요 없어짐) | CI lint 실패 |
| R6 | `diag()` 이벤트 문자열은 **이동해도 변경 금지** | `diff_trace.py` 실패 |

> R5가 핵심 지표다. 현재 **240건**의 지연 import 는 R1~R3 위반의 증상이다. 리팩토링 완료 = **240 → 0**.

---

## 2. 목표 디렉토리 구조

```
backend/app/
├── bootstrap/                    ← composition root (모든 모듈 배선 허용)
│   ├── main.py                     FastAPI app · 라우터 등록 · 미들웨어
│   ├── jobs.py                     APScheduler 배선  ← 현 scheduler/jobs.py (614)
│   ├── config.py                   Settings
│   ├── factory.py                  Provider 생성   ⚠ §5-1 참조 (실질 무의미 → 흡수 검토)
│   └── database.py                 엔진/세션 + init_db(386) ⚠ 분해 대상
│
├── core/
│   ├── models/                   ← db/models.py 603 (Q4 결정 대기: 분할 여부)
│   ├── tenant/                     tenant_context · api/deps · auth/*
│   ├── reservation/                reservation_mutator (FIELD_PERMISSIONS · ChangeSource)
│   ├── calendar/                   stay_logic · schedule_utils · ★stay_coverage_filter
│   ├── chip/                       chip_store · chip_reconciler
│   ├── vocabulary/                 section_registry · party_type · room_grade
│   ├── lifecycle/                  reservation_lifecycle · reconcile(레지스트리화)
│   │                               + ★reconciler_registry (신규)
│   └── observability/              diag_logger · activity_logger · event_bus
│
└── modules/
    ├── room_assign/    room_assignment(1110) · room_auto_assign(666) · invariants ·
    │                   room_lookup · dorm_gender · password_display ·
    │                   api/rooms(956) · api/reservations_room · api/buildings
    ├── sms_send/       sms_sender · real/sms · renderer · variables ·
    │                   api/reservations_sms · ★api/templates (M3→M2 재배치)
    ├── scheduling/     template_scheduler(867) · schedule_manager ·
    │                   filters(스케줄 파서부) · api/template_schedules · api/scheduler
    ├── custom_sends/   surcharge · party3_mms · room_upgrade_{common,promise,review}
    ├── naver/          naver_sync(1008) · real/reservation
    ├── party_ops/      api/{party_checkin,party_hosts,daily_host,daily_review,
    │                        onsite_female_invite,cleancrew}
    ├── stay_group/     consecutive_stay(445) · split_group_guard(613) · api/reservations_stay
    ├── reporting/      api/{sales_report,dashboard,activity_logs}
    ├── event_sms/      api/event_sms · event_sms_hook
    └── reservation_api/ api/reservations(669) · reservations_shared · shared_schemas
                         + api/{auth,settings,tenants,events}
```

### 이동 중 발생하는 두 개의 분할

| 원본 | 분할 |
|------|------|
| `services/filters.py` (541) | **`core/calendar/coverage.py`** ← `stay_coverage_filter` · `activity_stats_filter` (6개 모듈이 씀)<br>**`modules/scheduling/filter_parser.py`** ← v1/v2 dual-parse · assignment/column_match |
| `services/custom_schedule_registry.py` | **`core/lifecycle/reconciler_registry.py`** ← 등록/디스패치<br>**`modules/custom_sends/registration.py`** ← 5종 실제 등록 |

---

## 3. 위반 전수 등록 — **77건**

> **정정 (2026-08-06)**: 최초 수동 집계는 **67건**이었으나, `api/reservations*` 계열(`reservation_api`)을 집계에서 제외한 undercount였다.
> `scripts/arch/check_layers.py` 실측 결과 = **77건** (R2 코어→모듈 13 · R3 모듈→모듈 64).
> 앞으로 이 숫자의 권위는 **검사기**다. 손으로 세지 않는다.

실측: 모듈→모듈 **64건** + 코어→모듈 **13건**. 아래 9패턴으로 분류된다.

### 패턴 A — `stay_coverage_filter` 오배치 (7건) · 난이도 ⬜ 낮음

`filters.py` 를 M3로 뒀지만 실제로는 **6개 모듈이 공유하는 날짜 축 쿼리**다.

| 위반 | 사용 심볼 |
|------|-----------|
| `sms_sender.py:291` | `stay_coverage_filter` |
| `templates/variables.py:158, :201` | `stay_coverage_filter`, `activity_stats_filter` |
| `party3_mms.py:56` | `stay_coverage_filter` |
| `api/party_checkin.py:63` | `stay_coverage_filter` |
| `api/dashboard.py:57` | `stay_coverage_filter`, `activity_stats_filter` |
| `chip_reconciler.py:267` | `stay_coverage_filter` |

**해결**: `core/calendar/coverage.py` 로 이동. 순수 파일 이동 + import 경로 변경 = **no-op 보장**.
※ `stay_coverage_filter` 는 stay-semantics 설계안이 지정한 **SQL 단일 진실**이므로 코어 배치가 원설계와도 일치.

---

### 패턴 B — 커스텀 reconciler 하드 import (21건) · 난이도 🟥 높음 ← **최대 덩어리**

M4의 5종 reconciler를 M1·M5·C6가 **private 함수까지 직접 import** 한다. `room_assignment ↔ reconcile` 순환의 실체.

| 방향 | 건수 | 대표 |
|------|------|------|
| M1 → M4 | **14** | `room_assignment.py:448/455/456, :652~654, :721~723` → `_delete_all_surcharge_chips`, `_delete_all_room_upgrade_{promise,review}_chips`<br>`room_auto_assign.py:116/125/126` → `reconcile_*_batch`<br>`api/rooms.py:371/372` → `reconcile_*_batch` |
| C6 → M4 | 4 | `reconcile.py:39~42` → 4종 reconciler (지연 import + "순환 회피용" 주석) |
| M5 → M4 | 3 | `naver_sync.py:434/443/444` → `reconcile_*_batch` |

**해결 — 레지스트리 역전 (`custom_schedule_registry` 의 이미 검증된 패턴을 확장)**:

```python
# core/lifecycle/reconciler_registry.py  (코어 — 모듈을 모름)
RECONCILERS: dict[str, ChipReconciler] = {}
def register(custom_type: str, r: ChipReconciler) -> None: ...
def reconcile_all(db, reservation_id, dates=None, room_id=None) -> None:  # 전체 디스패치
def reconcile_batch(db, reservation_ids, dates) -> None:                   # 배치 디스패치
def delete_all_chips(db, reservation_id, dates) -> None:                   # _delete_all_* 통합

# modules/custom_sends/registration.py  (모듈 — 코어에 자기를 등록)
register("surcharge_standard", SurchargeReconciler())
register("party3_today_mms",   Party3MmsReconciler())
...
# bootstrap/main.py 가 startup 시 import → 등록 발생
```

호출처는 전부 `reconciler_registry.reconcile_all(...)` 한 줄로 바뀐다.
⚠️ **`_delete_all_*_chips` 3종을 하나로 합칠 때 삭제 범위가 각각 다른지 먼저 확인 필요** (§6 미해결 항목).

---

### 패턴 C — `jobs.py` 는 모듈이 아니라 composition root (9건) · 난이도 ⬜ 낮음

`scheduler/jobs.py`(614)는 APScheduler에 **모든 모듈의 작업을 배선**하는 파일이다. M3로 분류하면 영원히 위반이다.

| 위반 | 대상 |
|------|------|
| `jobs.py:73, :211, :300` | `naver_sync.sync_naver_to_db` (M5) |
| `jobs.py:256, :299` | `real.reservation.RealReservationProvider` (M5) |
| `jobs.py:16` | `room_auto_assign.daily_assign_rooms` (M1) |
| `jobs.py:168` | `consecutive_stay.detect_and_link_consecutive_stays` (M7) |
| `jobs.py:417` | `split_group_guard.sweep_orphan_groups` (M7) |
| `jobs.py:384` | `templates.variables.refresh_snapshot` (M2) |

**해결**: `bootstrap/jobs.py` 로 이동 → R4에 의해 전부 합법. **파일 1개 이동으로 9건 소멸.**
※ 역방향 1건은 별도: `api/dashboard.py:77` 이 `jobs.scheduler` 객체를 직접 import → **스케줄러 상태 조회 API를 코어 observability 또는 모듈 공개 API로 노출**해야 함.

---

### 패턴 D — 레지스트리 자체가 모듈에 있음 (4건) · 난이도 ⬜ 낮음

| 위반 | 심볼 |
|------|------|
| `api/template_schedules.py:53, :255` | `CUSTOM_SCHEDULE_TYPES`, `get_custom_types` |
| `template_scheduler.py:371, :533` | `get_pre_send_refresh_handler`, `is_per_date_dedup` |

**해결**: 패턴 B의 `core/lifecycle/reconciler_registry.py` 에 흡수. 레지스트리는 코어, 등록은 모듈.

---

### 패턴 E — 단순 오배치 (3건) · 난이도 ⬜ 낮음

| 위반 | 해결 |
|------|------|
| `api/templates.py:15, :522` → `templates/renderer`, `templates/variables` | `api/templates.py` 는 **템플릿 CRUD** = M2 소속. M3(스케줄링)로 잘못 분류한 것 |
| `template_scheduler.py:797` → `room_lookup.batch_room_number_map` | `room_lookup` 은 3개 모듈(M1/M3/M6)이 쓰는 조회 헬퍼 → **core** 승격 후보 |
| `api/party_checkin.py:123` → `room_lookup.batch_room_number_map` | 위와 동일 건 |

---

### 패턴 F — 진짜 모듈 간 협력 (23건) · 난이도 🟥 높음 ← **설계 필요**

패턴 A~E로 44건이 사라지고 **남는 23건이 진짜 문제**다. 전부 "한 모듈의 작업이 다른 모듈의 후처리를 유발" 하는 구조.

| # | 방향 | 위반 | 성격 |
|---|------|------|------|
| F1 | M5 → M7 | `naver_sync.py:16, :284, :328, :931` — `compute_is_long_stay`, `detect_and_link_consecutive_stays`, `unlink_from_group`, split alert 5종 | 동기화 후 연박/분할 재계산 |
| F2 | M5 → M1 | `naver_sync.py:17` — `auto_assign_rooms` | 동기화 후 자동 배정 |
| F3 | M5 → M9 | `naver_sync.py:456` — `schedule_event_sms_hook` | 신규 예약 즉시 발송 |
| F4 | M7 → M1 | `api/reservations_stay.py:167, :288, :367` — `assign_room`, `unassign_dates` | 연장/축소 시 배정 이동 |
| F5 | M9 → M3 | `event_sms_hook.py:85` — `TemplateScheduleExecutor` | 훅이 스케줄 실행기 재사용 |
| F6 | M9 → M2 | `event_sms_hook.py:173` — `send_single_sms` | |
| F7 | M3 → M2 | `template_scheduler.py:21` — `send_single_sms` | 스케줄 → 발송 |
| F8 | M2 → M4 | `templates/variables.py:266` — `_is_double_room`, `compute_guest_count`, `compute_excess`, `_is_dormitory_reservation` | 🔴 템플릿 변수 계산이 surcharge **내부 함수** 4개를 직접 사용 |
| F9 | M6 → M1 | `api/party_checkin.py:123` | 패턴 E와 중복 |
| F10 | M8 → M3 | `api/dashboard.py:77` | 패턴 C 잔여 |
| F11 | M4 → M3 | `party3_mms.py:56` | 패턴 A로 해소됨 |

**해결 후보 (택1 필요 — §6 Q8)**:
- **(가) 코어 이벤트 버스** — `core/lifecycle` 이 `on_reservation_synced` 등 이벤트를 발행, 모듈이 구독. F1~F3 에 적합. 실행 순서 보장이 과제
- **(나) 공개 API 계약** — 모듈마다 `modules/X/public.py` 를 두고 **거기만** 다른 모듈이 import 허용 (R3 완화). 가장 현실적이나 규칙이 약해짐
- **(다) 코어로 승격** — F7(`send_single_sms`), F8(surcharge 계산기) 처럼 여러 모듈이 쓰는 것은 코어로 올림

**F8은 별도 취급 필요**: `variables.py` 가 `surcharge` 의 **private 함수 4개**(`_is_double_room`, `_is_dormitory_reservation`)를 쓴다. 이건 배치 문제가 아니라 **surcharge 모듈의 계산 로직이 공개 계산기로 분리돼야 한다**는 신호.

---

### 패턴 G — bootstrap 예외 처리 (2건) · 난이도 ⬜ 낮음

`factory.py:15` → `real.sms` · `factory.py:30` → `real.reservation`.
`bootstrap/` 배치로 R4에 의해 합법. ⚠️ 단 §5-1 참조.

---

### 패턴 H — 공용 API 계약이 모듈 안에 있음 (6건) · 난이도 ⬜ 낮음 ← **검사기가 새로 발견**

`api/shared_schemas.py` (7줄, `ActionResponse` 하나)를 **5개 모듈이 import** 한다. 7줄짜리 파일 때문에 5건 위반.

| 위반 | 심볼 |
|------|------|
| `api/buildings.py:11` · `api/rooms.py:18` (M1) | `ActionResponse` |
| `api/template_schedules.py:17` (M3) | `ActionResponse` |
| `api/templates.py:16` (M2) | `ActionResponse` |
| `api/reservations_stay.py:17` (M7) | `ActionResponse` |
| `api/reservations_room.py:16` (M1) | `ReservationResponse`, `_to_response` ← 이건 별건, 아래 |

**해결**: `core/api_contracts.py` 로 승격. 파일 이동 1회로 5건 소멸.

`api/reservations_shared._to_response`(131줄)는 성격이 다르다 — **예약 응답 직렬화의 단일 소스**다.
→ `core/reservation/serialization.py` 승격 후보. 단 `reservations_shared.py:81` 이 `templates.variables._inject_surcharge_vars` 를 지연 import 한다(§F8과 동일한 leak). **`product_capacity` 코어 승격이 선행되면 함께 풀린다.**

---

### 패턴 I — `room_assignment.py` 가 코어 프리미티브를 품고 있음 (5건) · 난이도 🟥 높음 ← **검사기가 새로 발견**

`core:lifecycle → module:room_assign` 5건은 패턴 B(레지스트리)로 풀리지 않는다. 코어 lifecycle 이 호출하는 건 **커스텀 reconciler 가 아니라 room_assignment 의 내부 프리미티브**다.

| 위반 | 호출 심볼 |
|------|-----------|
| `reconcile.py:38` | `sync_sms_tags` |
| `reservation_lifecycle.py:45` | `_shift_daily_records`, `_reconcile_dates` |
| `reservation_lifecycle.py:76` | `check_assignment_validity` (`room_assignment_invariants`) |
| `reservation_lifecycle.py:77` | `unassign_room` |
| `reservation_lifecycle.py:241` | `clear_all_for_reservation` |

전부 **지연 import** — "순환 회피용"이라는 주석이 붙은 그 순환이다.

**진단**: `room_assignment.py`(1110줄)는 두 가지가 섞여 있다.
- **코어 프리미티브** — 예약 날짜 변경 시 일자별 레코드를 밀고(`_shift_daily_records`) 정합화(`_reconcile_dates`)하는 것. 이건 M1 고유 기능이 아니라 **예약 라이프사이클의 일부**
- **모듈 로직** — 실제 배정 알고리즘(`assign_room` 357줄), 도미토리 성별 잠금, 용량 체크

**해결**: `room_assignment.py` 를 **분할**한다.
```
core/reservation/daily_records.py   ← _shift_daily_records · _reconcile_dates ·
                                       clear_all_for_reservation · unassign_room · sync_sms_tags
modules/room_assign/service.py      ← assign_room · 배정 알고리즘 · 무결성 가드
```
⚠️ 분할선이 정확한지 **호출 관계를 먼저 확인해야 한다** (§6 조사항목 I-1).

---

### 요약 (검사기 실측)

| 패턴 | 건수 | 난이도 | 해결 수단 |
|------|------|--------|-----------|
| A. stay_coverage 오배치 | 7 | ⬜ | 파일 이동 → `core/calendar` |
| **B. 커스텀 reconciler** | **21** | 🟥 | 레지스트리 역전 |
| C. jobs.py 오분류 | 9 | ⬜ | 파일 이동 → `bootstrap` |
| D. 레지스트리 오배치 | 4 | ⬜ | B에 흡수 |
| E. 단순 오배치 | 4 | ⬜ | 파일 이동 |
| G. factory | 2 | ⬜ | 파일 이동 (Q9 대기) |
| **H. 공용 API 계약** | **6** | ⬜ | `core/api_contracts` 승격 |
| **I. room_assignment 분할** | **5** | 🟥 | 코어 프리미티브 분리 |
| **F. 진짜 모듈 간 협력** | **19** | 🟥 | 이벤트 + 코어승격 + public.py |
| 계 | **77** | | |

> **32건(42%)은 파일 이동만으로 사라진다** (A·C·E·G·H).
> 설계가 필요한 건 B(21) + I(5) + F(19) = **45건**. 그중 B는 이 프로젝트에 이미 검증된 레지스트리 패턴이 있다.

---

### 패턴 F 해소 전략 배정 (Q8 결정 = 혼합)

| # | 위반 | 건수 | 전략 |
|---|------|------|------|
| **F1** | `naver_sync` → `consecutive_stay`·`split_group_guard` (`:16 :284 :328 :931`) | 4 | 🔵 **코어 이벤트** |
| **F2** | `naver_sync:17` → `room_auto_assign.auto_assign_rooms` | 1 | 🔵 **코어 이벤트** |
| **F3** | `naver_sync:456` → `event_sms_hook.schedule_event_sms_hook` | 1 | 🔵 **코어 이벤트** |
| **F3b** | `api/reservations:229/384/410/444/454/533/596` → stay_group | 7 | 🔵 **코어 이벤트** (F1과 동일 성격 — 예약 변경 후처리) |
| **F6** | `event_sms_hook:173` → `send_single_sms` | 1 | 🟢 **코어 승격** → `core/sms` |
| **F7** | `template_scheduler:21` → `send_single_sms` | 1 | 🟢 **코어 승격** (동일) |
| **F8** | `templates/variables:266` → surcharge 계산기 4종 | 1 | 🟢 **코어 승격** → `core/vocabulary/product_capacity` |
| **F4** | `api/reservations_stay:167/288/367` → `assign_room`·`unassign_dates` | 3 | 🟡 **public.py 계약** (API 요청 내 동기 호출 — 결과를 즉시 응답해야 함) |
| **F5** | `event_sms_hook:85` → `TemplateScheduleExecutor` | 1 | 🟡 **public.py 계약** |
| **F10** | `api/dashboard:77` → `jobs.scheduler` | 1 | 🟢 **코어 승격** → 스케줄러 상태를 `core/observability` 로 노출 |
| **F11** | `api/settings:8/396/397` → naver (쿠키 검증/수동 동기화) | 3 | 🟡 **public.py 계약** ※ 또는 settings 를 모듈별로 분산 |
| 계 | | **19+** | |

**이벤트 버스 설계 요건** (P4 착수 전 확정 필요):
- `core/lifecycle` 에 `on_reservation_synced` / `on_reservation_changed` 이벤트 추가
- ⚠️ **실행 순서를 명시적으로 선언**해야 한다 — 현재 `naver_sync` 의 호출 순서(연박 링크 → 자동배정 → 칩 reconcile → 이벤트 SMS)에 의존성이 있음
- ⚠️ **diag 시퀀스 순서가 보존돼야 한다** (R6) — `diff_trace.py` 가 순서까지 비교하는지 확인 필요 (§6 조사항목)
- ⚠️ 예외 전파 — 현재 `event_sms_hook` 은 fire-and-forget(호출자 보호). 이벤트 버스가 이 semantics 를 구독자별로 표현할 수 있어야 함

---

## 4. 단계 분해 원칙 (기존 mutator/lifecycle plan 계승)

1. **모든 단계는 no-op** — 값·동작 동등만. 버그 수정은 절대 섞지 않는다
2. **매 단계마다**: 전체 테스트 스위트(baseline 동일) + `diff_trace.py` 로 diag 시퀀스 동일 증명
3. **diag 문자열 동결** — 파일이 이동해도 이벤트명 불변 (R6)
4. **역행 불가 지점 없음** — 각 단계는 독립 커밋, revert 가능
5. **잠재버그 발견 시 등록만** — stay-semantics 의 `LB-xx` 레지스터 방식 계승, 수정은 사람 결정 후 별도 커밋

### 잠정 순서

| Phase | 내용 | 위반 해소 | 리스크 | 상태 |
|-------|------|-----------|--------|------|
| **P0** | 계층 검사기 + baseline + diag 스냅샷 | 0 | 없음 | ✅ **완료** |
| **P1** | 디렉토리 골격 생성 + **re-export shim** 배치 (기존 경로 전부 살아있음) | 0 | 낮음 | |
| **P2** | 패턴 A·C·E·G·H — 순수 파일 이동 **28건** | 28 | 낮음 | |
| **P3** | 패턴 B·D — 레지스트리 역전 **25건** | 25 | **높음** | |
| **P4** | 패턴 I — `room_assignment` 분할 **5건** | 5 | **높음** | |
| **P5** | 패턴 F — 이벤트 + 코어승격 + public.py **19건** | 19 | **높음** | |
| **P6** | shim 제거 + 지연 import 239 → 0 + baseline 비움 | — | 중간 | |
| **P7** | CLAUDE.md 재작성 + `docs/pipelines/` 갱신 + backend-map 부활 | — | 없음 | |

### P0 산출물 (완료, 2026-08-06)

```
scripts/arch/check_layers.py    계층 규칙 검사기 (R1~R6)
scripts/arch/baseline.txt       현재 위반 65키 (77건이 심볼단위로 중복제거된 수)
scripts/arch/diag_events.json   diag 이벤트 199종 스냅샷 (R6 동결 기준)
```

기준선 (2026-08-06):

| 지표 | 현재 | 목표 |
|------|------|------|
| 계층 위반 | **77** | 0 |
| 지연 import (R5) | **239** (38파일) | 0 |
| diag 이벤트 (R6) | **199종** | 199종 (불변) |

사용:
```bash
python scripts/arch/check_layers.py            # 요약 + baseline 대조
python scripts/arch/check_layers.py --list     # 위반 전수
python scripts/arch/check_layers.py --ci       # 신규 위반/diag 소실 시 exit 1
```
검사기는 **이동 전/중/후 모두 동작**한다 — `app.core.*` / `app.modules.*` / `app.bootstrap` 은 경로에서 계층을 유도하고, 아직 안 옮긴 파일은 `LEGACY_PLACEMENT` 표에서 목표 계층을 조회한다. 파일을 옮기면 그 표에서 해당 줄을 지우면 된다.

---

## 5. 리팩토링과 함께 정리될 부수 항목

### 5-1. 죽은 추상화 — `providers/base.py` + `factory.py`
Mock 구현이 전부 제거되어 Protocol 이 **구현체 1개짜리 인터페이스**다. `factory.py:15/30` 의 유일한 역할은 tenant 설정 주입.
→ **선택**: (ⓐ) Protocol 유지 (테스트 더블 여지) / (ⓑ) 제거하고 모듈이 직접 생성 / (ⓒ) `bootstrap/` 에 흡수. §6 Q9.

### 5-2. `db/database.init_db` 386줄
런타임 자동 마이그레이션이 부트스트랩 함수에 통째로 있다. Alembic 이 이미 있는데 이중화.
→ 리팩토링 범위에 포함할지 §6 Q10.

### 5-3. 거대 함수 10개
`sync_naver_to_db`(420) · `assign_room`(357) · `execute_schedule`(295) · `_update_reservation`(265) · `update_reservation`(250) 등.
→ **이동과 분해를 같은 단계에 섞지 않는다.** P2~P4는 이동만, 분해는 P7 이후 별도.

### 5-4. 동명 함수 7쌍
`ensure_chip`/`remove_chip` (chip_store ↔ room_upgrade_common) 는 패턴 B에서 자연 해소 예상.
`preview_targets` (api/template_schedules ↔ template_scheduler) 는 API가 로직을 재구현했는지 확인 필요.

---

## 6. 사람이 결정해야 할 것 (다음 입력)

| # | 질문 | 영향 | 상태 |
|---|------|------|------|
| **Q8** | 패턴 F 해소 방식 | P5 | ✅ **혼합** — 이벤트(F1~F3b) + 코어승격(F6~F8·F10) + public.py(F4·F5·F11) |
| **Q13** | P0 lint 도구 | — | ✅ **자체 AST 스크립트** (`scripts/arch/check_layers.py`) |
| **Q9** | `providers/base.py` + `factory.py` 죽은 추상화를 유지/제거/흡수? | 소 | 대기 |
| **Q10** | `init_db` 386줄 자동 마이그레이션을 이번 범위에 포함? | 중 | 대기 |
| **Q11** | `db/models.py` 603줄 24모델을 도메인별 분할? (fan-in 55 — 전 파일 import 변경) | 대 | 대기 |
| **Q12** | `api/reservations*` 5분할 유지 vs `modules/reservation_api/` 재편? | 중 | 대기 |
| **Q14** | `api/settings.py` — 테넌트 설정(코어)과 네이버 쿠키 검증(M5)이 한 파일. 분할? | 소 | 대기 |

### 조사 완료 (2026-08-06)

#### ✅ B-1 — `_delete_all_*` 3종 통합 **가능**

제네릭이 **이미 존재**한다: `room_upgrade_common.delete_all_chips(db, res_id, date, custom_type, *, diag_prefix)`.
- `room_upgrade_promise` / `room_upgrade_review` 는 이미 이걸 호출하는 얇은 래퍼
- `surcharge._delete_all_surcharge_chips` 만 **인라인 복제** 상태 (동일 로직을 직접 작성)
- 유일한 차이: surcharge 는 custom_type 2개(`_ALL_SURCHARGE_TYPES`)를 한 번에 처리

→ **해결**: 시그니처를 `custom_types: Sequence[str]` 로 확장해 `core/lifecycle/reconciler_registry.delete_all_chips` 로 승격. `diag_prefix` 파라미터가 이미 있어 **R6(diag 문자열 보존) 자동 충족**.

#### 🔴 F8-1 — 순수 계산 **아님**. 그리고 소비자가 3곳 (예상보다 큼)

| 함수 | 순수성 | 실체 |
|------|--------|------|
| `compute_guest_count(reservation)` | ✅ 순수 | party_size ?? male+female ?? 1 |
| `_is_double_room(db, room)` | ❌ DB | `RoomBizItemLink` 조회 → `DOUBLE_ROOM_BIZ_ITEM_IDS` 대조 |
| `_is_dormitory_reservation(db, reservation)` | ❌ DB | `naver_biz_item_id` → 매핑 객실이 전부 도미토리인가 |
| `resolve_product_base_capacity(db, res, room)` | ❌ DB | `NaverBizItem.default_capacity` 우선 (업그레이드 대응) |
| `compute_excess(db, res, room)` | ❌ DB | 위 둘의 조합 |

**소비자가 3곳이다** (설계안 작성 시 2곳으로 알았던 것보다 많음):
1. `surcharge.py` — 소유자
2. `room_upgrade_common.py:117` — **`decide_upgrade_eligible` 이 지연 import 로 `_is_dormitory_reservation`·`compute_guest_count`·`resolve_product_base_capacity` 사용** (M4 내부라 위반 집계엔 안 잡혔음)
3. `templates/variables.py:266` — F8 위반 본체

→ 이건 "surcharge 의 내부 함수" 가 아니라 **"예약상품(NaverBizItem) ↔ 객실(Room) 의 용량·등급 판정"** 이라는 독립 도메인이다. 주석에도 명시돼 있다:
> *"무료 업글 안내(약속/객후) 발송 ⇔ 추가금(surcharge) 미발생 AND 등급 상승"*

**해결**: **`core/vocabulary/product_capacity.py` 신설** (신규 코어 — §2 구조에 추가).
`room_grade.py` 와 같은 층. surcharge · room_upgrade_* · variables 셋 다 여기에 의존하게 되어 F8 + M4 내부 지연 import 가 동시 해소된다.
⚠️ DB 의존이므로 "코어는 순수해야 한다" 규칙은 두지 않는다 — 코어도 `Session` 을 받는다 (`chip_store` 와 동일 선례).

#### E-1 — `room_lookup` 코어 승격
`Room`/`RoomAssignment` 모델 의존은 문제없음. `chip_store`(코어)가 이미 `ReservationSmsAssignment` 에 의존하는 것과 동일 선례. **코어도 모델에 의존한다**(`core/models` 는 최하위 층).

### 남은 조사 항목 (P3~P5 착수 전)

- **I-1** — `room_assignment.py`(1110줄)의 분할선 검증: `_shift_daily_records` / `_reconcile_dates` / `unassign_room` / `clear_all_for_reservation` / `sync_sms_tags` 가 `assign_room` 계열과 **상태를 공유하는지**. 공유하면 단순 분할 불가
- **R6-1** — `diff_trace.py` 가 diag 이벤트의 **순서까지** 비교하는지. 순서를 본다면 이벤트 버스(P5)에서 구독자 실행 순서를 현재 호출 순서와 정확히 일치시켜야 함
- **F1-1** — `naver_sync` 의 후처리 호출 순서(연박 링크 → 자동배정 → 칩 reconcile → 이벤트 SMS)에 **실제 데이터 의존성이 있는지**. 있으면 이벤트 버스에 우선순위 선언이 필요
- **B-2** — `preview_targets` 가 `api/template_schedules.py:569` 와 `template_scheduler.py:784` 에 각각 있음. API 가 로직을 재구현했는지 위임인지
