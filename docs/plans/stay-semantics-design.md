# Stay Semantics 재정립 설계안 (당일 vs 숙박 / check_out_date)

> ⚠️ **2026-08-31**: 잔여 작업(Phase B·D)은 **전면 리팩토링 P5.5 로 흡수** — [`refactor/05-stay-개념설계.md`](./refactor/05-stay-개념설계.md) · [`refactor/07-계획갱신-2026-08-31.md`](./refactor/07-계획갱신-2026-08-31.md) §5. 이 문서는 배경 자료로만 유지.

> 상태: **설계안 (구현 전)** · 작성 2026-06-19 · 브랜치 `feat/activity-product`
> 방식: section_registry / party_type 와 동일 — **단일 명세 + 특성화 테스트 + no-op 교체 + 프론트 미러 drift-guard**
> 근거: 8각도 전수조사(120 findings, 10 agents) + 적대적 completeness critic + 직접 코드 재검증

> **결정(2026-06-19)**: ① **범위 = Phase A(no-op) 먼저**, 잠재버그(§5)는 그 다음 별도. ② **정규화(§7-1) = mutator 단일소스** (`apply_changes` old!=new 비교 전 `''→None`, LB-04/05 동시해결) — 단 Phase C 에서 적용(no-op 아님), prod 백필은 사람 수동.
> **순환참조 해소**: `stay_logic.py` 는 **순수 leaf(datetime 만)** — `is_single_day_stay`/`stay_nights` 만. `date_range` 는 schedule_utils 에 물리적 잔류(re-export 안 함 — re-export 하면 stay_logic→schedule_utils→stay_logic 순환). 호출처는 date_range 를 기존대로 schedule_utils 에서 import.

---

## 0. 목적 & 원칙

`check_out_date` 의 NULL / `''` / 날짜 해석("당일 1박" vs "숙박/연박")이 **5계열 술어로 혼재**되어 있고, 역사적으로 사이드이펙트가 많았던 영역이다. 목표:

1. **기능 100% 유지** — 혼재한 개념을 깔끔한 단일 로직으로 재정립하되, 동작은 보존(no-op).
2. **구조 개선 + 확장성** — 캐노니컬 헬퍼 1세트 + 프론트 미러 + drift-guard + 불변식 문서화.
3. **잠재 버그 발굴 & 재발 방지** — 지금 조용히 잠재한 사이드이펙트/에러/코너케이스를 **별도 레지스터(LB-01..12)** 로 드러내고, 고칠지 말지는 **사람이 결정**.

> ⚠️ **핵심 분리 원칙**: "안전한 no-op 통합"(§4)과 "잠재버그 수정"(§5)은 **절대 섞지 않는다.** no-op 단계는 값-동등만 수행하고, 버그는 특성화 테스트로 *현재(버그 포함) 동작을 핀* 한 뒤 사람 결정 후 별도 커밋.

---

## 1. 캐노니컬 모델 (확정)

| 개념 | 정의 |
|------|------|
| **당일(1박)** | `not check_out_date` (NULL 또는 `''`) **또는** `check_out_date == check_in_date`. 체크인일이 유일·마지막 박일. |
| **숙박(연박)** | `check_out_date` truthy **AND** `check_out_date > check_in_date`. 박 집합 = 반열림 `[check_in, check_out)` — **체크아웃일 제외**. |
| **체크아웃일** | 박이 아님(이미 떠난 날). extend_stay 는 이 규약의 따름정리: 옛 checkout 이 새 박, checkout+1. |
| **nights** | `max(1, (check_out - check_in).days)`, NULL/''/co≤ci → 1. |
| **last_night** | 숙박: `check_out - 1일`; 당일: `check_in`. |
| **first_night** | `check_in` (체크아웃 산술 없음, NULL/''-safe). |
| **stay_dates** | `date_range(check_in, check_out)` (반열림, 체크아웃 제외, NULL/''/co≤ci → `[check_in]`). |

### `''` 의 의미 (버그 클래스의 뿌리)
- **의미상**: `''` = NULL = 당일 1박. Python truthiness 독자(`not check_out_date`)는 전부 이렇게 취급 → **safe**.
- **SQL/identity 상**: `''` 은 NULL 과 **다른** 정렬가능 비-NULL 값. `'' IS NULL`=false, `'' > date`=false(사전식, Postgres·SQLite 동일), `func.max` 가 `''` 채택. → `is_(None)`/`isnot(None)`/`func.max`/등치비교 사이트는 **`''` 에서 갈라짐**.
- **`''` 의 유일한 출처**: `real/reservation.py:364 _format_date` 가 빈/파싱불가 날짜에 **`''`(None 아님)** 반환. 네이버 경로(`naver_sync.py:715/786`)는 `or None` 으로 정규화하지만 **수동 경로(POST create `reservations.py:222`, PATCH `reservations.py:340`→mutator)는 정규화 안 함** → 수동으로 `''` 가 영구 저장 가능.

### 이미 존재하는 캐노니컬 자산 (재사용)
| 자산 | 위치 | 비고 |
|------|------|------|
| `date_range(from, end)` | `schedule_utils.py:51` | 반열림 박 생성기, `not end or end≤from → [from]`. **'' /co≤ci-safe.** 진짜 단일 진실. |
| `stay_coverage_filter(d)` | `filters.py:58/74` | SQL 트윈. `or_(and_(ci≤d, co>d), ci==d)` — `ci==d` 분기가 NULL/''/co==ci 흡수. |
| `last_night_of_stay(res)` | `room_upgrade_common.py:33` | **Reservation 객체** 인자. ⚠️ **co==ci 가드 누락(LB-02)** — 캐노니컬과 비동등. |

---

## 2. 현재 코드 지형 — 술어 5계열

| 계열 | 형태 | `''` 처리 | 대표 사이트 |
|------|------|----------|-------------|
| **(1) 정규 truthiness** | `not co or co == ci` | safe | `schedule_utils.py:25`, `template_scheduler.py:844` (§6-A 주석) |
| **(2) bare truthiness** | `co and co > ci` | safe | `schedule_utils.py:46`, `room_auto_assign.py:342/399`, `sales_report.py:135` |
| **(3) `is None` ⚠️** | `co is None` / `.is_(None)` | **'' 누락** | `room_auto_assign.py:249`, `consecutive_stay.py:355`, 다수 SQL |
| **(4) date-diff** | `(co-ci).days` + `max(1,·)` 또는 `>1` | NULL→1(safe) | `variables.py:242`, `event_sms.py:126`, `reservations_shared.py:239`, `consecutive_stay.py:43`(long-stay, **다른 임계**) |
| **(5) SQL coverage** | `is_(None) OR co>d` (±`ci==d`) | `ci==d` 있으면 safe, 없으면 '' 누락 | `filters.py:74`(canonical), `reservations.py:70/84`, `rooms.py:401`, `naver_sync.py:495`, `room_auto_assign.py:519`, `sales_report.py:112`, `consecutive_stay.py:84/98`(의도적 `isnot(None)`) |

**Python coverage 인라인 복제(같은 모양, drift 위험)**: `sales_report.py:135-136`, `party3_mms.py:168`, `room_auto_assign.py:249`.
**인라인 박-범위 루프**: `reservations_stay.py:359-364`(reduce), `:186`(extend collapse).
**범위 소비처(미감사)**: `reservations_room.py:61/78/131` `end_date = co if apply_subsequent else None` raw 전달.

> ※ `room_assignment.py:842/908` 은 **이미 `_date_range`(=date_range alias) 호출** → 통합 대상 아님(직접 확인).

---

## 3. 제안 API — `backend/app/services/stay_logic.py` (신규 leaf 모듈)

> **leaf 제약**: `datetime` 외 `app.*` import 금지. `schedule_utils` 가 이걸 import 해도 순환참조(room_assignment→chip_reconciler→template_scheduler→room_assignment, `schedule_utils.py:3-5` 주석) 재발 안 함. `date_range` 는 **물리적으로 schedule_utils 에 잔류**, stay_logic 이 import 후 re-export.

| 헬퍼 | 시그니처 | 의미 | 교체 대상(byte-equiv 만) |
|------|----------|------|--------------------------|
| `is_single_day_stay` | `(ci, co) -> bool` | `not co or co == ci`. 계열(1) 추출. | `schedule_utils.py:25`, `template_scheduler.py:844` |
| `stay_nights` | `(ci, co) -> int` | `max(1,(co-ci).days)`, NULL/''/예외→1. **돈 계산(variables:304) 먹임 — max(1,·) floor 보존 필수(LB-08 마스킹)**. | `variables.py:242`(thin wrapper 유지), `event_sms.py:126`†, `reservations_shared.py:239`† |
| `last_night_of_stay_str` | `(ci, co) -> str?` | 당일→ci, 숙박→co-1일. **신규 — 기존 어느 사이트와도 비동등**(room_upgrade_common 은 객체인자+co==ci 가드 없음). | (신규, 위 §5 LB-02 결정 후 적용) |
| `date_range` | (기존) | re-export only. | 신규 인라인 루프 차단 + 문서화 |
| `stay_coverage_filter` | (기존 SQL) | 단일 SQL 진실로 지정. canonical-shape(`filters.py:74` 패밀리)만 위임. | `reservations.py:70` |

† `event_sms`/`reservations_shared` 는 try/except 범위(`ValueError` only vs `ValueError+TypeError`)·`fromisoformat` vs `strptime`·그룹 offset 누적 차이가 있어 **증명된 경우만** 교체, 아니면 인라인 유지(critic 지적 — `reservations_shared:237-241` 은 그룹 누적 루프 내부라 naive swap 위험).

**프론트 미러 `frontend/src/lib/stayLogic.ts` (신규) + drift-guard**:
| 헬퍼 | 통합 대상 | 주의 |
|------|-----------|------|
| `stayNights(ci?, co?)` | — | 백엔드 `stay_nights` 미러 |
| `isMultiNight(res)` | `useGuestMove.ts:23`(`diff>1`), `GuestRow.tsx:118`(`>=2`), `MobileGuestRow.tsx:91` | **`stay_group_id` OR-절 보존**(날짜함수 아닌 그룹축 — useGuestMove.ts:20). GuestRow/Mobile 은 **완전 동일 아님**(GuestRow 는 `stay_group_total_nights` 분기 추가 보유) — 공유 블록만 교체. |
| `nextCheckinDate(res)` | `useStayGroup.ts:19`(`(co&&co!==ci)?co:ci+1`) | `StayGroupChainModal.tsx:114` 라벨 불일치(LB-11)는 12b(사람 결정). |

---

## 4. 무중단(no-op) 마이그레이션 순서 — *값-동등만*

| # | 파일:라인 | Before → After | risk | 동등성 근거 |
|---|-----------|----------------|------|-------------|
| 1 | `stay_logic.py` (신규) | 모듈 생성(date_range re-export + is_single_day_stay/stay_nights). | low | importer 0, 캐노니컬 사이트에서 byte 복사. |
| 2 | `tests/unit/test_stay_logic.py` (신규) | 특성화 테스트(§6 매트릭스). **현재(버그포함) 출력을 핀.** | low | 테스트만. |
| 3 | `template_scheduler.py:844` | `not co or co==ci` → `is_single_day_stay(ci,co)` | low | 동일 truthiness·동일 '' 처리. |
| 4 | `schedule_utils.py:25` | (last_night 분기) → `is_single_day_stay(...)` | low | 같은 사이트에서 추출. leaf 라 순환참조 무. |
| 5 | `event_sms.py:126` | `max((co-ci).days,1)` → `stay_nights(...)` | med | †except 범위 동등 증명 후. 아니면 skip. |
| 6 | `variables.py:242` | `_calculate_stay_nights` 본문 → `stay_nights(...)` (이름/시그 유지 wrapper) | med | **돈 계산 — max(1,·) floor 보존, byte-identical 청구**. |
| 7 | `reservations.py:70` | 인라인 `or_(and_(ci≤d,co>d),ci==d)` → `stay_coverage_filter(date)` | med | `filters.py:74` 와 동일 트리. SQLite+Postgres 양쪽 진리표 검증. |
| 8 | `reconcile.py:51` 등 | date_range import 경로를 stay_logic re-export 로(선택, cosmetic). | low | 같은 함수 객체. 순환참조 안 건드릴 때만. |
| 9 | `frontend/src/lib/stayLogic.ts` (신규)+drift-guard | FE 미러 + 공유 fixture 로 FE==BE 핀. 호출처 미연결. | low | 추가만. sectionSpec 패턴. |
| 10 | `useGuestMove.ts:23` | `diff>1` → `isMultiNight(res)` (stay_group OR 보존) | med | `>1`==`>=2`(정수 diff) drift-guard 확인. |
| 11 | `GuestRow.tsx:118` (+`MobileGuestRow.tsx:91` 동시) | 단일-record `<2` 블록만 미러로. **GuestRow 그룹분기 미수정.** | med | `stayNights==diff`, `<2`==`!isMultiNight`. 2파일 lockstep. |
| 12a | `useStayGroup.ts:19` | `nextDateOf` 본문 → `nextCheckinDate(res)` | low | `(co&&co!==ci)?co:ci+1` 동일. |

> **드롭됨(critic 정정)**: `room_assignment.py:842/908`(이미 canonical), `room_upgrade_common.last_night_of_stay`(비동등, §5 LB-02), `is_(None)` SQL 사이트 일괄교체(§5 / risk).

---

## 5. 잠재버그 레지스터 — *사람 결정 (fix-now vs preserve)*

> no-op 단계는 이 중 **무엇도 자동 수정하지 않는다.** 각 항목은 특성화 테스트로 현재 동작을 핀 → 결정 후 별도 처리.

| ID | 위치 | 증상 / 시나리오 | 심각도 | 권장 |
|----|------|----------------|--------|------|
| **LB-01** | `real/reservation.py:364` | `_format_date` 가 빈 날짜에 `''` 반환 — 전체 '' 클래스의 뿌리. | high | `None` 반환으로 변경 + prod 백필(사람 수동, 로컬=prod 금지). |
| **LB-02** | `room_upgrade_common.py:33` | `last_night_of_stay` 가 **co==ci 가드 누락** → 비-NULL 당일행에 `ci-1일`(투숙 전날) 반환 → 업그레이드 객후 칩이 비-투숙일 타겟 → 미발송. (`_validate_dates` 가 co==ci 허용) | high | `is_single_day_stay` 가드 추가. |
| **LB-03** | `room_upgrade_common.py:43` | co<ci 무검증 → `co-1일`(체크인 이전) 반환. 단일필드 PATCH 로 도달가능. | med | co<ci 가드 → ci(또는 None). |
| **LB-04** | `reservations.py:340` (mutator) | PATCH `check_out_date:''` 가 raw 저장 + **`co != old` 라 `check_out_pinned=True` 자동설정** → '' 영구 핀 + 네이버 정정 차단. | **critical** | mutator `apply_changes` 의 old!=new 비교 **전**에 '' →None 중앙 정규화(naver 와 패리티). |
| **LB-05** | `reservations.py:222` | POST create 가 body `check_out_date` raw 저장(네이버 create 는 `or None`). 외부 API/폼이 `''` 보내면 저장. | high | LB-04 와 동일 중앙 정규화 또는 pydantic field_validator. |
| **LB-06** | `template_scheduler.py:834` | 그룹 last-night = `func.max(co)` + `isnot(None)`. (a) lone '' → `strptime('')` 크래시. (b) **NULL-checkout 가 진짜 마지막인 그룹** → 비-마지막 멤버 + NULL 멤버 둘 다 발화 → **last_night 이중발송**. | high | 멤버별 effective last-night(NULL/''→ci) 기반 + strptime '' 가드. §7 그룹권위 결정. |
| **LB-07** | `schedule_utils.py:27` vs `template_scheduler.py:850` | 칩생성=멤버 OWN checkout(is_last_in_group), 발송=그룹 `func.max`. 불일치 시 칩 생성일≠발송 필터일 → **silent 미발송**. first_night 도 역방향 비대칭. | med | 그룹 last/first 정의 단일화(§7 권위 결정 필요). |
| **LB-08** | `variables.py:242` | `_calculate_stay_nights` `max(1,diff)` 가 co<ci/'' 를 **조용히 1박 청구**. 유일한 돈-곱셈(variables:304). | med | floor 유지(현행 금액 보존) vs co≤ci 에러/로그 — **금액 영향, 사람 결정**. |
| **LB-09**(정정) | `consecutive_stay.py:84/98` | 자동연결 스캔이 **명시적 `isnot(None)`** 로 NULL 다박만 대상(누락가드 아님 — 의도적). 단 `''` 은 not-NULL 이라 통과 후 `'' >= today` 사전식 false 로 드롭. NULL/'' 1박행은 설계상 범위밖. | med | 설계의도 확인 — '' coalesce 여부 결정. |
| **LB-10** | `consecutive_stay.py:180` vs `:355` | 자동연결(`co==ci`만)과 수동검증(NULL 1박도 브리지, 단 `is None` 라 '' 미브리지→오거부) 불일치. | low | 양쪽 `is_single_day_stay` 기반 브리지로 통일(동작변경). |
| **LB-11** | `StayGroupChainModal.tsx:114` | 라벨 `co || ''` 가 `nextDateOf`(co==ci→ci+1)와 불일치 → 라벨일≠로드일. (+'' 면 빈 라벨) | low | 12b: 라벨도 `nextCheckinDate`. 표시변경. |
| **LB-12** | `useReservationForm.ts:187` | FE 1박 표현 3종 공존(co=ci+1 / co==ci(DateChangeModal) / NULL(네이버)). | low | 한 표현 채택(§7 co==ci 결정). |

**critic 추가 코너케이스**: StayGroupChainModal '' → 빈 라벨; 비-zero-padded `'2026-1-9'` 가 `is_(None)` 계열 SQL 사전식 비교(`room_auto_assign:521`, `naver_sync:496`, `consecutive_stay:85/99`, `sales_report:113`, `rooms:403`) 전반 오정렬; co<ci 가 extend/reduce `:361` while 루프에서 zero-date 제거(음수 범위).

---

## 6. 특성화 테스트 코너케이스 매트릭스 (현재 동작 핀 — 버그 포함)

| 케이스 | 현재 동작(핀 대상) |
|--------|--------------------|
| `co = NULL` | single=True, nights=1, range=`[ci]`, last=ci. |
| `co = ''` | Python: single=True/nights1/range`[ci]`. **SQL**: `is_(None)` 드롭, `''>date`=false. (양쪽 DB 핀) |
| `co == ci` | single=True, range=`[ci]`, nights1. **BUT** `room_upgrade_common.last_night_of_stay`=`ci-1일` ← **LB-02 버그 핀**. |
| `co < ci` | range=`[ci]`(중화), nights=1. **BUT** last=`co-1일`(투숙전) ← LB-03 핀. money=1박 ← LB-08 핀. |
| 그룹 NULL-last 멤버 | last_night 이중발송 ← LB-06 핀(통합테스트). |
| 그룹 own vs max | 칩일≠발송일 ← LB-07 핀. |
| `'2026-1-9'`(비패딩) | 사전식·strptime 오동작 핀(또는 캐노니컬에서 ISO assert — §7 결정). |
| `co = ci+1` vs NULL | nights/range 동일, 표시/체인/diff 만 상이(LB-12). |

---

## 7. 사람이 결정해야 할 것 (Open Questions)

1. **정규화 범위** — `''→None` 을 write 경계(create + mutator)에서 차단할까? **이 한 방이 '' 클래스 전체를 닫지만 no-op 아님**(수동 저장값 변경). ⓐ지금 정규화 ⓑ현행 보존 ⓒ헬퍼 내부만. → **권장 ⓐ(mutator 단일소스, LB-04/05 동시해결)** 단 prod 백필 별도.
2. **SQL '' 의미** — 캐노니컬 SQL 트윈을 '' -safe 로 만들까(7+ 사이트 동작변경) vs 현행 보존. → no-op 은 canonical-shape 만, 나머지는 LB 로.
3. **co==ci 표현** — 1박을 NULL / co==ci / co=ci+1 중 어느 표준으로? (표시·체인·diff 영향, 동작변경.)
4. **그룹 last-night 권위** — OWN checkout(칩측) vs `func.max`(발송측) 중 무엇이 정답? (LB-06/07 핵심.)
5. **long-stay 분리 확정** — `(co-ci).days>1`(2박+)은 single-vs-multi 와 다른 임계 → 별도 유지(헬퍼에 안 섞음).
6. **날짜포맷 보증** — 캐노니컬 헬퍼가 ISO zero-pad assert/normalize? vs `String(20)→Date` 마이그(models:113 TODO)에 위임.

---

## 8. 재발 방지 & 확장성

- **불변식 등재**: `docs/diag-golden/invariants.md`(**기존 파일, 5.1KB**)에 "체크아웃 배타 반열림 `[ci,co)`, NULL/''/co==ci=1박" 을 명명 불변식으로 추가 + 헬퍼 docstring 에서 역참조.
- **프론트 미러 + drift-guard**: `stayLogic.ts` ↔ 백엔드를 **공유 fixture(코너케이스 매트릭스 JSON)** 로 강제(section/party_type 패턴).
- **SQL↔Python 교차검증 테스트**: `stay_coverage_filter` 와 `party3_mms.py:168` Python 미러를 같은 날짜로 돌려 동일 멤버십 assert(미래 drift 차단).
- **Postgres Date 전환 대비**(models:113 TODO): 전환 시 '' 저장 불가 → 모든 `is_(None)` 자동 정상화. 단 **선행 백필(''→NULL)** 필요(사람 수동, 로컬=prod 금지). 헬퍼는 `date|str|None` 수용 가능하게.

---

## 9. 리스크 (naive trap)

1. `is_(None)` SQL 사이트 일괄 캐노니컬 교체 = '' 동작 변경(현재 '' 드롭) → **byte-identical 사이트만 교체**.
2. `room_upgrade_common.last_night_of_stay` 추출 시 캐노니컬(가드 보유) 드롭인 = LB-02 **조용한 수정** = 동작변경 → 현행 유지.
3. `stay_nights` 의 `max(1,·)` floor 제거 = **금액 변경**(LB-08) → 정확히 보존.
4. mutator 중앙 정규화 = "그냥 청소"처럼 보이나 수동 저장값·핀 동작 변경(LB-04/05) → 사람 게이트.
5. **Postgres vs SQLite**: 테스트는 SQLite, prod 는 Postgres. '' 사전식은 양쪽 일치 가정이나 **미검증**(로컬=prod, write 스크립트 금지) → step7 은 disposable/read-only Postgres 로 별도 검증.
6. FE 중복 drift(GuestRow/Mobile), stay_group 축 누수(isMultiNight), 순환참조(leaf 위반), **특성화 테스트는 이상이 아닌 버그를 핀**해야 no-op 증명 성립.

---

## ✅ 진행 현황 (2026-06-19)

- **Phase A 백엔드 완료** (커밋 `ad07e5b`): stay_logic.py + 특성화 15 + 치환 5사이트. 전체 551 passed(baseline 동일) + 독립 적대검증 6/6 NO-OP.
- **Phase A 프론트 부분 완료**: `stayLogic.ts` 미러 생성 + `useGuestMove.isMultiNight`(step10)·`useStayGroup.nextDateOf`(step12a) 치환(verbatim 복사+별칭 import, tsc 통과).
  - **step11(GuestRow/MobileGuestRow stayProgress) 보류**: `totalNights` 가 배지 분모로 직접 표시되어(`${currentNight}/${totalNights}`) 표시 결합도 높음 → 별도 후속(저위험·저가치).
  - **drift-guard 미적용**: 프론트 vitest 미설치 → 백엔드 stay_logic.py 를 단일 사양으로 cross-ref(§8). vitest 도입 시 공유 fixture drift-guard 추가.
- **Phase C 착수 — LB-04 수정 완료**: mutator `apply_changes` 에 `check_out_date=='' → None` 정규화(단일소스). 4링크 전수확인(직접추적+적대 refuter): 진짜 버그(단 **LATENT** — 현재 FE caller는 '' 미전송, 직접 API/향후 회귀로만 트리거). check_in_date(nullable=False)는 제외. 테스트 5 + 전체 556 passed(baseline 동일). 동작변경(no-op 아님) — '' 헛된 핀 제거 + 클린 None 저장.
- **LB-05 수정 완료**: POST create 생성자에 `check_out_date=reservation.check_out_date or None`(naver_sync:715 미러). 4링크 확인(추적+refuter): REAL but **LATENT**(현 FE 미전송, 직접 API만), LB-04보다 경severity(핀 없음·크래시 없음). 엔드포인트 직접호출 테스트 3 + 전체 559 passed.
- **남음**: Phase B(§7 나머지: co==ci표현/그룹last권위/SQL''-safe/날짜ISO) → 기타 LB(02 high 등) → Phase D(불변식 등재 + SQL↔Python 교차테스트). prod 백필('' →NULL)은 사람 수동.

## 10. 권장 실행 단계

1. **Phase A (no-op)**: §4 step1~12a. 각 단계 후 전체 스위트(baseline 4 fail/2 err) + 별도 verifier 적대검증. → 커밋.
2. **Phase B (결정)**: §7 6개 + §5 LB 중 수정대상 사람 확정.
3. **Phase C (fix)**: 확정분만 별도 커밋(LB-04 mutator 정규화부터 권장 — 뿌리). prod 백필은 사람 수동.
4. **Phase D**: 불변식 등재 + SQL↔Python 교차테스트 + diag-golden 반영.
