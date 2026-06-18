# 액티비티(Activity) 상품 기능 — 설계안 (v3, 2차 심층검증 반영)

> 작성: 2026-06-18 (v3: 2026-06-19) · 상태: 설계 검토(미착수) · 관련: `docs/plans/unified-room-edit-modal-design.md`
>
> **검증 이력**: v1(초안) → v2(1차 적대리뷰: 코드오류 5+리스크 9) → v3(2차 심층: 가드 위치/범위 3건 정정 + 진입점 다수) → **v3-final(3차 좁은검증: 6 미수렴 중 5 코드로 닫힘, §6-A 정정, 신규 local 2건 흡수)**. 모든 file:line 은 `main` @ eb57bd1 기준, **3회 코드 재검증 완료**. 착수 전 재확인 권장.
>
> **판정: 착수 가능 상태**(재설계 불필요). 아키텍처(section='activity' 행 추가, 마이그레이션 0)는 3회 재확인된 유효 토대. §9 체크리스트는 라인 단위로 확정(mutator-style 사전조사 충족). **핵심 결정 모두 확정**(D1~D4/D6/D8). 나머지 D7/D9/D10 은 Phase 0 dump 또는 권장 기본값. Phase 0 런타임 5건(§부록 B)은 비블로커 사전점검.
> **수렴 상태**: 3차는 "닫는 단계" — 새 카테고리 없음, 신규는 local fix 2건(Reservations 라벨 low / sales_report dedup med)뿐. Phase 1+2 원자배포로 착수.

---

## 0. TL;DR — 세 질문 + 정정 요약

| 질문 | 결론 |
|------|------|
| **Q1. 별도 테이블 vs 행 추가** | **기존 `Reservation` 에 `section='activity'` 행 추가**(마이그레이션 0). 2차 재확인. |
| **Q2. 충돌/추가 연동** | 충돌은 *조용한 오발송/통계오염/배치크래시* 형태. 핵심: **표준 SMS 발송이 칩 가드를 우회**(`is_custom` 분기) → 가드는 칩 레이어 아닌 **`filters.apply_structural_filters`** 에. 인원/예약수 통계 누수는 **백엔드 6곳**(gender SUM 4 + dashboard count 1 + recent list 1) + **프론트 2곳**(roomTotal + unstable). `check_out_date` WRITE 진입점 **5곳**, `section` WRITE 진입점 **5곳**. |
| **Q3. 독립/연동 + 파티 추후신청** | 2층 구조 + D8=Option A(deliberate party_type=완전합류→party3 일관발송). 단 **effective party_type 은 4시스템 모두 `COALESCE(daily, Reservation.party_type)`** 로 통일해야 silent drift 없음. NULL gender→SUM 0계상 엣지 주의. |

**v2→v3 핵심 정정 5건 (모두 코드 재검증)**:
1. **§6-I 가드 위치 오류**: 표준 스케줄 발송은 칩을 안 거치고 `Reservation` 직접쿼리(`template_scheduler.py:455-457`, 칩 prefilter 는 `if is_custom:` L464 안에서만). → 가드를 `chip_reconciler` 아닌 **`filters.apply_structural_filters`(filters.py:441)** + event base query 에.
2. **§4-14/D3 과잉가드**: `sales_report.py:141` 은 `party_type` 게이트(L144)가 이미 미참여 activity 배제 → 무조건 `section=='activity'` 제외는 중복+D8 위반. **삭제**.
3. **§6-A 진입점 누락**: `check_out_date` WRITE 는 naver _create/_update 외에 **`reservations_stay.py:224`(extend)/`:426`(reduce)** 2곳 더(check_out_pinned 박음). `_update` 정규화는 gate 때문에 `= None` 직접대입 + **legacy '' backfill** 필요. `_filter_last_day:838` 는 `''` 에 `strptime` 크래시.
4. **§6-G 누수 범위**: dashboard 는 gender SUM(L60-61) 외 **today_reservations count(L29-33) + recent list(L37-39)** 도 section-blind. 프론트도 unstable 루프(2번째 SUM) 누락.
5. **§6-H 가드 방식**: `assign_room` 은 section 대입(:532) **전에** RoomAssignment 행 생성+reconcile → "필드만 보호"로는 자동격리 깨짐. **진입부 거부(raise/early-return)** 확정.

---

## 1. 요구사항
1. 객실 숙박 무관 단독 예약(객실 예약자/미예약자 모두).
2. 동일 네이버 업체 별도 biz_item. 인입 시 객실배정 페이지 표시.
3. '액티비티' 행: `이름 / 연락처 / 액티비티(파티 대신) / 성별+인원수 / 예약객실(상품명) / 메모 / 문자`.

**함의**: 객실+액티비티 신청자는 **별 예약 2건**(같은 phone). 단독은 `check_out_date` 없음 / `RoomAssignment` 0 / `room_id=null`.

---

## 2. 현재 구조 — 핵심 사실 (2차 재검증)

### 2-1. section + mutator (LIVE)
- `Reservation.section = Column(String(20), default='unassigned')` — enum/CHECK 없음, 마이그레이션 불필요.
- 인입: `naver_sync.py:682` `section = section_hint if in ('party','room','unstable') else 'unassigned'`(단일 진입점). `_update` 는 section 미변경(보존, 재확인).
- **mutator 는 LIVE**: `reservations.py:339`(MANUAL), `naver_sync.py:754/773/806`(NAVER), `reservations_stay.py:224/426`(MANUAL) 가 `apply_changes` 호출. `FIELD_PERMISSIONS['section']`(L58)=`{NAVER:never, MANUAL:always, SYSTEM:always}`. `check_out_date`(L39)=`{NAVER:guarded, MANUAL:always, SYSTEM:always}` + pin(L70). → section MANUAL/SYSTEM, check_out MANUAL 이 자유 통과.

### 2-2. section WRITE 진입점 — 통합표 (전수, 5곳)
| # | 위치 | 방식 | activity clobber | 가드 |
|---|------|------|------------------|------|
| 1 | `room_assignment.py:532` | 직접대입 `='room'` | 수동배정 시 영구전이 | §6-H 진입부 거부 |
| 2 | `room_assignment.py:374` | 직접대입 `='unassigned'`(push-out) | 도미토리 밀림 | §6-H |
| 3 | `naver_sync.py:717` | 생성자 `section=` | 화이트리스트 누락 시 강등 | §4-1 |
| 4 | `reservations.py:339` | mutator setattr(MANUAL) | PATCH activity→room/party | §6-B (mutator 내부 가드) |
| 5 | `reservations.py:223` | POST 생성자 `section=` | 잘못된 section 입력 | §6-B |
> `.section=` 직접대입은 grep 상 정확히 :374/:532 두 곳뿐(확인). 나머지는 생성자/mutator. split sibling 은 activity 미생성(`_has_room_link=False`, L595).

### 2-3. check_out_date WRITE 진입점 — 통합표 (전수, 5곳)
| # | 위치 | activity 위험 | 가드 |
|---|------|--------------|------|
| 1 | `naver_sync.py:706` `_create` | provider 가 `''` 반환 → `''` 저장 | §6-A `''→None` |
| 2 | `naver_sync.py:806` `_update` | gate(L777)는 `''` 로 통과(현행 no-op 무해), stored-only None 화 시 재발화 | §6-A incoming+stored 원자 정규화 |
| 3 | `reservations_stay.py:224` extend | `apply_changes` + `check_out_pinned=True`(L226) → 이후 NAVER 정규화 차단 | §6-A 진입부 거부 |
| 4 | `reservations_stay.py:426` reduce | 동일 + pin(L441) | §6-A 진입부 거부 |
| 5 | `reservations.py` PATCH | MANUAL:always → `''`/임의 날짜 | §6-B 흐름 |

### 2-4. SMS/칩/통계 — 발송 경로 정정
- **표준 발송은 칩을 안 거침(핵심)**: `_get_targets_standard`(`template_scheduler.py:455-457`) base query = tenant+status 만. 칩 prefilter(`Reservation.id.in_(eligible_ids)`)는 **`if is_custom:`(L464) 안에서만**. 표준 스케줄은 `Reservation` 직접쿼리 → `_apply_structural_filters`(L510→`filters.py:441`) → 빈 필터면 `.filter` 미부착(`filters.py:489`) → **activity 통과 → 객실 SMS({{room_num}} 빈값) 실발송 → `record_failed` 보호칩(`assigned_by='failed'`) 영구잔류**. ⇒ §6-I.
- **gender SUM 누수 4곳**: `variables.py:167-168/204-205`, `template_scheduler.py:395-399`, `dashboard.py:60-61`. ⇒ §6-G.
- **dashboard count/list 누수**: `dashboard.py:29-33` today_reservations(`func.count`, section-blind, naver_split 만 제외), `:37-39` recent_reservations. ⇒ §6-G/D9.
- **수동 칩 API**: `reservations_sms.py:53`(sms-assign)/`:119`(sms-toggle)가 `chip_store.ensure_chip` 직통 + `send_single_sms` → activity 에 객실 템플릿 즉시발송, 보호칩. ⇒ §6-I.
- **event 즉시발송**: `_get_targets_event`(`template_scheduler.py:690-727`)는 structural filter 미적용 → §6-J opt-in 불가, base query 별도 가드 필요.
- **party3 2진입점**: `reconcile.py:76`(예약-centric) + `custom_schedule_registry.py:103`→`party3_mms.py:48`(schedule-centric). D8=Option A 이라 **차단 안 함**(§4-11 default 상속만 차단).
- **last_night 크래시**: `_filter_last_day`(`template_scheduler.py:838`)는 `''` 가 `is None`/`==check_in` 둘 다 False → `strptime('')`(L852) ValueError, try/except 없음 → 그 스케줄 전체 미발송. ⇒ §6-A.
- **자동격리 확인**: `surcharge/room_upgrade_*`(RoomAssignment 부재 no-op — **단 §6-H 로 RoomAssignment 행 생성을 막아야 유효**), room SUM(room_id JOIN), `consecutive_stay`(check_out **None** 제외 — `''` 는 미해당), 취소(status 게이트), 멀티테넌트(section 무관, `tenant_context` 에 section 0건).

---

## 3. Q1 — 행 추가 채택 (재확인)
별도 테이블 반대. `section` 자유값(마이그레이션 0), 7컬럼 데이터 존재(`reservations_shared.py:255-300`), GET `/api/reservations` 배정무관 반환, `GuestRow` 7컬럼+zone prop. 향후 회차/정원/정산은 `ActivityProduct` 비파괴 추가 슬롯(YAGNI).

---

## 4. Q2 — 충돌/연동 맵 (v3 정정)

### 필수 (Phase 1+2 원자배포)
| # | 위치 | 변경 | 미수정 증상 | 등급 |
|---|------|------|------------|------|
| 1 | `naver_sync.py:682` | 화이트리스트 `'activity'` | 신규생성 unassigned 강등 | High |
| 2 | `room_auto_assign.py:232` | `notin_([...,'activity'])` | 매일 자동배정 실패+critical diag/SSE 알람 스팸 | High |
| 3 | gender SUM 4곳 (§6-G) | `variables.py:167-168/204-205`, `template_scheduler.py:395-399`, `dashboard.py:60-61` | 파티/성별 SMS·대시보드 차트 오염 | High |
| 4 | **`filters.apply_structural_filters`(filters.py:441)** (§6-I) | 표준 스케줄 activity 조건부 제외 | **무필터 표준 스케줄이 activity 에 객실 SMS 실발송** | High |
| 5 | **`template_scheduler.py:690-727`** `_get_targets_event` | base query section 가드 | event 객실 환영문자 즉시 오발송 | High |
| 6 | **`reservations_sms.py:53/119`** | activity×객실템플릿 거부 | 수동 SMS 토글 즉시 오발송 | High |
| 7 | §6-A `check_out` 정규화 5진입점 (`''→None`) | + `_filter_last_day:838` 방어 + legacy backfill | 다일칩/통계+last_night 배치 크래시+매 sync 재발화 | High |
| 8 | **`room_assignment.py:532` `assign_room`** (§6-H) | 진입부 activity **거부**(필드보호 아님) | RoomAssignment 행 생성→자동격리 붕괴+영구전이 | High |
| 9 | `reservations_stay.py:224/426` | extend/reduce 진입부 activity 400 거부 | check_out 오염+pin | High |
| 10 | ~~party3 blanket~~ | **Option A: 차단 안 함** | — | (폐기) |
| 11 | `naver_sync.py:684-687` | `default_party_type` 자동상속 `section!='activity'` 가드 (**Option A 핵심**) | party 자동노출+MMS 실수발송 | High |
| 12 | `event_sms.py:57-63,119-149` | `section!='activity'` 필터 | 동일 phone 박수합산/명단 오염 | Med |
| 13 | `consecutive_stay.py:382-420` | `link_reservations` activity 거부 | 수동 연박묶기 강제편입 | Med |
| 14 | ~~`sales_report.py:141`~~ | **가드 불필요** — party_type 게이트(L144)가 미참여 activity 자동배제 (§8-D3) | — | (폐기) |
| 15 | `reservations.py:292` | `section_labels['activity']` | 로그 가독성 | Low |

### 선택/점검
- `filters.py:48,290-312` — 전용 발송 시 `'activity'` assignment 분기(§6-J). 단 event 는 opt-in 불가(§8-D10).
- `filters.py:49` column_match / 상품명 네이밍 격리.
- `reservations.py:160-163` `has_unstable` 배지 cross-section 오표시 좁힘.

---

## 5. Q3 — 독립/연동 + Option A

**독립**: `section='activity'`, `biz_item_name`, `male/female_count`, `notes`, `sms_assignments`.
**연동(per-date)**: 파티 추후신청 = `ReservationDailyInfo.party_type`. 기본 미신청 = `default_party_type=NULL`(+§4-11 코드가드).

**통계(D1/D2)**: activity 인원은 그 날짜 effective party_type ∈ `{'1','2','2차만'}` 일 때만 SUM 포함.
- ⚠️ **effective party_type 키 통일(필수)**: §6-G 통계 가드는 **`COALESCE(ReservationDailyInfo.party_type, Reservation.party_type)`** 로 평가해야 함. party3/party_checkin/sales_report 가 모두 이 COALESCE 를 쓰는데(`party_checkin.py:96`, `sales_report.py:143`, `party3_mms.py:90`), 통계만 daily-only 키면 — 운영자가 PATCH 로 `Reservation.party_type='2'` 직접세팅(daily 아님) 시 *발송·명단엔 잡히나 통계엔 안 잡히는 silent drift*. (또는 activity 의 `Reservation.party_type` 직접 PATCH 자체를 §6-B 류로 차단.)

**D8 = Option A**: deliberate party_type = 완전합류 → 통계포함 + party_checkin 등장 + party3 MMS 일관발송. party3 blanket 차단 폐기(§4-10), `default_party_type` 자동상속만 차단(§4-11).
- ⚠️ **엣지1(stay_coverage)**: 통계/party3 base 가 `stay_coverage_filter(date)` → activity 는 자기 check_in 날짜만 후보. 다른 날짜 daily party_type 은 SUM/party3 미포함(활동=단일일정 전제상 보통 OK, 명시 한계).
- ⚠️ **엣지2(NULL gender → 0계상)**: `_init_gender_counts` 가 gender≠'남'/'여' 시 `(None,None)` 반환 → `func.sum` 이 NULL 무시 → "완전합류"가 통계상 **0명**으로 조용히 샘. participant_count=male+female 도 0. → D7(성별 수집) 미해결 시 합류 인원이 0 계상됨을 명시.

---

## 6. 가드 상세

### A. `check_out_date` 정규화 — 5진입점 + 방어 + backfill
- `''→None` **section 무관 공통 헬퍼**(provider 가 `''` 반환하는 PRE-EXISTING 버그라 비-activity 도 정규화 권장).
- `_create_reservation`(naver_sync.py:706) + `_update_reservation`: ⚠️ **정정** — provider 가 `''` 반환이라 `if incoming_end is not None`(L777) gate 는 `''` 로 **통과**한다(현행 `''==''` mutator no-op 이라 무해). 그러나 **stored 만 `None` 직접대입하면** `'' != None` → `on_dates_changed`(L935) 매 sync 재발화(불필요 reconcile+diag 노이즈). → **incoming 과 stored 의 `''→None` 정규화를 원자적 짝으로**(gate 진입 전 incoming 정규화, 또는 activity 는 mutator 호출 자체 skip). 'gate 밖 None 단독대입' 금지(mutator old=None,new='' 로 재오염). 단 재발화해도 activity 에서 crash 는 없음(shift/reconcile 모두 falsy no-op, 확인).
- `reservations_stay.py:224/426` extend/reduce: 진입부 `section=='activity'` → 400 거부(UI 숨김 §6-D 는 보조).
- **legacy `''` backfill**(Phase 1+2): `UPDATE reservations SET check_out_date=NULL WHERE section='activity' AND check_out_date=''` (ORM, **Supabase pooler readonly 금지**).
- **`_filter_last_day`(template_scheduler.py:838) 방어**: `if not res.check_out_date or res.check_out_date==res.check_in_date:` (`''` 도 1박취급, strptime ValueError 차단).

### B. section 전이 가드 — mutator 내부로
caller-site(reservations.py:339) 단일가드는 POST(:223)/SYSTEM 경로를 못 막음. → **`reservation_mutator.apply_changes` 내부 section 전용 가드**: `old=='activity' && new∈{room,party,unassigned} && source≠명시적 activity-clear` 거부. NAVER/SYSTEM/MANUAL 일괄 보호.

### C. 3번째 컬럼 — `party_type` 편집셀 유지
빈값 placeholder `"액티비티"`, `1/2/2차만` 편집=파티합류+통계포함. 상품명은 5번째 컬럼. (§6-D 가드와 짝.)

### D. 프론트 재배치 차단 — 함수명 기준
- `useGuestMove.ts` `handleDropOnRoom` / `handleDropOnParty` / `handleDropOnPool` / `handleDropOnZoneCrossDay` **4개 함수 진입부** `source.section==='activity'` → toast+return. (v2 의 라인범위 730-822 는 handleDropOnRoom/ZoneCrossDay 를 놓침.)
- `GuestRow.tsx`/`MobileGuestRow.tsx` `useDraggable disabled` 에 `section==='activity'`(현재 isCancelled 만).
- `RoomAssignment.tsx:594~` contextMenu — activity 시 `onExtendStay`/`onChangeDates`/`onLinkStayGroup` + **`onCopyToUnstable`('언스 파티참여')** 숨김.

### E. 매핑 UI — RoomSettings + Quick + 드롭다운
`section_hint=='activity'` biz_item room 링크 비활성화 **두 곳**(RoomSettings + `Quick/UnifiedRoomEditModal.tsx:352-369`). `section_hint` 입력 **free text→드롭다운** + `rooms.py:271` PATCH 백엔드 화이트리스트(오타 강등 방지). `default_party_type` 입력도 비활성화.

### F. 인원 enrichment — 도미토리 방식 + 성별(D7)
`naver_sync.py:159-167` `section_hint=='activity'` → `people_count=booking_count` + `_is_activity`(fallback=1 해소). `_is_activity`≠`_is_dormitory`. update 경로(`:826`)도 포함. 성별: 폼 수집 시 `_parse_gender_from_custom_form`, 아니면 예약자 성별+수동보정(D7). **NULL gender→0계상 엣지(§5)** 유의.

### G. 통계 SUM — 백엔드 6 + 프론트 2, COALESCE party_type, date+tenant JOIN
- **백엔드 gender SUM 4곳**(`variables.py:167-168/204-205`, `template_scheduler.py:395-399`, `dashboard.py:60-61`): 조건 `section != 'activity' OR COALESCE(daily.party_type, Reservation.party_type) IN ('1','2','2차만')`. **EXISTS/상관 서브쿼리**(LEFT JOIN 시 `date==target_date` + `tenant_id==Reservation.tenant_id` 결합 필수 — 카티전곱/cross-tenant 방지).
- **백엔드 count/list 2곳**: `dashboard.py:29-33` today_reservations, `:37-39` recent_reservations → D9 결정(naver_split 처럼 `section!='activity'` 권장).
- **프론트 2곳**: `RoomAssignment.tsx` summary `roomTotal`(~L955) + `unstable`(~L998) 루프 둘 다 `if(section==='activity') continue`. `onCopyToUnstable` 전달조건 `section!=='activity'` + 복사본 push 제외.

### H. `assign_room` — 진입부 거부 (필드보호 아님)
`room_assignment.py` 는 `:511-525` RoomAssignment 행 생성+db.add → `:532` section='room' → `:540` reconcile_all_chips 순. 필드만 보호하면 RoomAssignment 행이 남아 자동격리(surcharge/upgrade/room SUM/consecutive JOIN) 붕괴. → **`assign_room` 진입부 또는 `reservations_room.py` assign 엔드포인트에서 `section=='activity'` 면 raise/400 거부**. push-out(`:374`)도 보호. 거부는 `assign_room.enter`(room_assignment.py:248) **앞**에서 하되 silent 방지 위해 `diag('assign_room.activity_blocked', level='critical')` 추가(INV-2 enter/exit 짝은 enter 미진입으로 자동보장). auto 경로는 §4-2 로 후보제외 → 이 거부는 manual+extend_stay 경로만 발화.

### I. 표준 칩+발송 격리 — chokepoint = apply_structural_filters
가드를 칩 레이어 아닌 **`filters.apply_structural_filters`(filters.py:441)** 에: "표준 스케줄은 assignment 필터에 activity 명시 안 되면(빈 필터 포함) `section!='activity'` 강제, activity 명시 시만 opt-in." chip_reconciler·`_get_targets_standard`·schedule-centric 후보쿼리가 이 함수 공유 → 칩생성·표준발송 단일 격리. **event(`_get_targets_event`)는 structural filter 미적용 → base query 별도 section 가드.** 수동 칩 API(§4-6)는 별도(activity×객실템플릿 거부). §6-J opt-in 분기와 공존 명시.
> ⚠️ **구현 방식(diag 회귀 회피)**: assignment_conds 에 병합하면 빈필터 표준스케줄 전수에서 `filter.applied` conditions_count≥1 신규 emit → golden 회귀 오판. → **별도 `.filter(section!='activity')` + 전용 diag `filter.activity_excluded`(verbose)** 로 구현. `schedule-execute-no-targets.yaml` 에 CONDITIONAL(min:0) 등재.

### J. (선택) 전용 발송 — Phase 4
`filters.py:48,290-312` 'activity' 두 곳 + Templates UI + 전용 템플릿(객실변수 미사용). **event 는 opt-in 불가**(§8-D10).

### 기타
- status 대문자(MEMORY), pooler readonly 금지(MEMORY), `ActivityZone` 색토큰 + `rowZone='activity'` 배선.

---

## 7. 단계별 구현 계획

> **Phase 1(인입)+Phase 2(격리) 원자배포** 필수(격리 전 인입 윈도우 = 실 오발송 + stale failed 칩).

### Phase 0 — 선결조사 (read-only)
- 액티비티 상품 1건 sync dump: **D7**(인원별 성별 수집), 날짜 단일/범위, `_has_room_link=False`.
- **party3 템플릿 room-var dump**: 각 테넌트 `party3_today_mms` content 에 `{{room_num}}` 등 객실변수 사용 여부. (seed 0건 — 전부 런타임 DB 생성이라 코드검증 불가, dump 필수.) ⚠️ 빈객실 발송차단 자체는 `sms_sender.py:145-171` `_ROOM_VARS_REQUIRED` 가드의 **의도된 정상동작**(실발송 차단). 단 객실변수 사용 시 deliberate party_type activity 가 매번 `record_failed`+critical diag 노이즈 → 선택적 강화: `party3_mms` ensure_chip 단계에서 `section=='activity' && 템플릿이 room-var 사용` 이면 칩 skip.
- `'activity'` 전수 grep 체크리스트(§9) 확정.

### Phase 1+2 (원자) — 인입 + 격리 동시
- **인입**: §4-1 화이트리스트, §6-F enrichment(+update parity), §6-A `''→None`(create+update+stay 거부), §4-2 자동배정 제외, §6-H assign_room 거부, §6-B mutator section 가드, §4-15 라벨.
- **격리**: §6-G(백엔드 6 SUM/count, COALESCE+EXISTS), §6-I(`apply_structural_filters` + event + 수동칩 API), §4-11 default_party_type, §4-12 event_sms, §4-13 consecutive_stay, §6-A `_filter_last_day` 방어.
- **마이그레이션**: legacy `''` backfill(§6-A), **ParticipantSnapshot 강제 refresh**(`variables.py:162-163` existing 단락반환 → 오염 스냅샷 무효화).
- 검증: `ooo-chip-check`, `ooo-log-validation`, `room_assign_failed` 미발생.

### Phase 3 — 프론트 ActivityZone + 가드
- `useReservationsData.ts:217` 버킷(else 앞)+sectionOverrides 제외, `ActivityZone.tsx`(+`rowZone='activity'`), §6-C 컬럼, §6-G 프론트 2 SUM+onCopyToUnstable, §6-D 4 drop 함수+contextMenu, §6-E 매핑 2곳+드롭다운, **`Reservations.tsx:580` 객실셀에 activity 라벨**(미배정 오표시 방지 — `check_out` 빈값은 `fmtPeriod` 이미 안전, 추가 가드 불요), 배선.

### Phase 4 — 전용 발송 (D6, §6-J)
`filters.py` 'activity' + Templates UI + 전용 템플릿. event 는 §8-D10 결정 따름.

### Phase 5 — 통합검증
`ooo-log-validation` + `ooo-chip-check` + E2E + **배포전 윈도우 activity failed 칩 일회성 정리** + **diag-golden 신규 항목**(`§6-F _is_activity`, assign_room activity 거부, `§6-I` filter conditions, split skip 분류) + naver split `skip_activity` 카운터 분리.

---

## 8. 결정사항

**확정**
| # | 확정 |
|---|------|
| D1 | 통계 합산하되 effective party_type(COALESCE) ∈ {'1','2','2차만'} 일 때만 |
| D2 | per-date 인원 필드 신설 안 함 |
| **D3** | **정정**: `sales_report.py:141` 추가 가드 불필요 — party_type 게이트(L144)가 미참여 activity 자동배제, deliberate party_type 은 D8 정합상 포함이 정답 |
| D6 | 전용 SMS 필요 — 인프라 재사용 + §6-J + §6-I |
| D8 | **Option A**: deliberate party_type=완전합류 → party3 일관발송, default 자동상속만 차단(§4-11) |
| **D4** | **이중계상 = phone dedup(객실행 우선)**: 같은 phone 의 **비-activity 행이 명단에 있으면** activity 행 인원 미합산, **activity 만 명단에 있으면** 합산. `party_checkin.py:86-97` + `sales_report.py:134-146` 양쪽 동일. 행은 표시(체크인 가능)하되 headcount 에서 조건부 제외. phone 빈값은 각각 고유 취급. Option A 정합 |

**결정 필요**
| # | 결정사항 | 권장 |
|---|---------|------|
| **D7** | 액티비티 폼 인원별 성별 수집? (NULL→0계상 엣지 직결) | Phase 0 dump |
| **D9** | dashboard today_reservations count/recent list 에 activity 포함? | naver_split 처럼 제외 권장 |
| **D10** | event 경로 activity 처리(structural filter 미적용이라 opt-in 불가) | Phase 4 전까지 event=activity 전면차단(base query) 단순화 권장 |
| D5 | activity nextDay 컬럼 | 생략 |

---

## 9. 부록 — file:line 체크리스트

**백엔드 — 인입/분류/전이 (Phase 1+2)**
- `naver_sync.py:682` 화이트리스트 / `:159-167` enrichment(`_is_activity`) / `:826` update parity / `:684-687` default_party_type 가드
- `naver_sync.py:706` `_create` + `:806` `_update` check_out `''→None`(update 는 `=None` 직접대입)
- `reservations_stay.py:224`(extend)/`:426`(reduce) — 진입부 activity 400 거부
- `room_assignment.py:532` `assign_room` 진입부 거부 / `:374` push-out 보호 (§6-H)
- `room_auto_assign.py:232` `notin_([...,'activity'])`
- `reservation_mutator.py:58` — apply_changes 내부 section 전이 가드(§6-B)
- `reservations.py:292` `section_labels`; `:223` POST section(§6-B 흐름)

**백엔드 — 통계 (Phase 1+2)**
- gender SUM 4곳 `variables.py:167-168/204-205` · `template_scheduler.py:395-399` · `dashboard.py:60-61` — §6-G(COALESCE+EXISTS+date/tenant)
- `dashboard.py:29-33` today_reservations count · `:37-39` recent_reservations — D9
- `party_checkin.py:86-97` 명단 + `sales_report.py:134-146` 참여통계 — **D4 phone dedup(객실행 우선)**: 명단 내 비-activity phone 집합 구성 → activity 행이 그 집합에 있으면 headcount 미합산. 행은 표시. DTO 에 `section`(또는 counted 플래그) 추가 → 프론트 reduce 조건부 제외. phone 빈값=고유

**백엔드 — 칩/발송 (Phase 1+2)**
- `filters.py:441` `apply_structural_filters` — 표준 격리 chokepoint(§6-I)
- `template_scheduler.py:690-727` `_get_targets_event` — base query section 가드
- `template_scheduler.py:838` `_filter_last_day` — `''` 1박취급 방어
- `reservations_sms.py:53`(sms-assign)/`:119`(sms-toggle) — activity×객실템플릿 거부
- `event_sms.py:57-63,119-149` `section!='activity'` / `consecutive_stay.py:382-420` activity 거부
- party3: **차단 안 함**(Option A) — `default_party_type` 자동상속 차단(§4-11)이 핵심

**백엔드 — 마이그레이션/검증**
- legacy `''` backfill(ORM, pooler readonly 금지) · ParticipantSnapshot 강제 refresh
- diag-golden: `naver-sync-sub-events.yaml` split_summary 에 `skip_activity` 분리 + `_draft/assign-room-activity-blocked.yaml`(MANDATORY request.enter 400 + `assign_room.activity_blocked`, forbidden `assign_room.enter`) + `schedule-execute-no-targets.yaml` CONDITIONAL(`filter.activity_excluded`) + state.json pending(`mutator.skipped reason=section_locked`, `stay_group.validate_failed reason=activity_member`, `extend/reduce.activity_blocked`)

**프론트 (Phase 3)**
- `useReservationsData.ts:217` 버킷+sectionOverrides 제외 / 복사본 push activity 제외
- `ActivityZone.tsx`(PartyZone 복제 + `rowZone='activity'`) / `GuestRow.tsx:236`+`MobileGuestRow.tsx`(placeholder + useDraggable disabled section)
- `RoomAssignment.tsx:955` roomTotal + `~998` unstable summary 둘 다 activity continue / onCopyToUnstable 게이트
- `useGuestMove.ts` handleDropOnRoom/Party/Pool/ZoneCrossDay 4함수 activity 거부 / contextMenu(§6-D)
- `Quick/UnifiedRoomEditModal.tsx:352-369` + RoomSettings 매핑 가드 + section_hint 드롭다운
- `Reservations.tsx:580` 객실셀 — activity 라벨 분기(미배정 오표시 방지). `fmtPeriod` 는 무수정(이미 안전)
- 배선: `RoomAssignment.tsx:91-94/596/1070-1076`, `DesktopLayout.tsx:90-97/292-296`, `MobileLayout.tsx:157-161`, `types.ts:39`

**검증**: `ooo-chip-check`, `ooo-log-validation`, `docs/diag-golden/actions/*.yaml`

---

## 부록 B — 3차 좁은 검증 결과 (6항목 중 5 코드로 닫힘, 1 의사결정)
| # | 항목 | 결과 |
|---|------|------|
| 1 | party3 템플릿 room-var | **닫힘(가드 정상)** — `sms_sender.py:145-171` 가 빈객실 발송 차단(의도된 동작). content 사용여부만 Phase 0 dump(needs-runtime, 비블로커) |
| 2 | `_update` incoming_end gate | **닫힘+정정** — `''` 로 gate 통과하나 mutator no-op 무해. §6-A 를 incoming+stored 원자 정규화로 수정 완료(위) |
| 3 | `Reservations.tsx` 전역목록 | **닫힘** — `fmtPeriod` 이미 안전(크래시 없음). 객실셀 activity '미배정' 오표시만 라벨 1분기로 fix(§7 Phase 3, low) |
| 4 | 이중계상 | **닫힘** — `party_checkin.py` + **`sales_report.py:134-146`(동반 발견)** 둘 다 phone dedup 없음. **D4 확정 = phone dedup(객실행 우선, 명단 기준)**: 비-activity 행이 명단에 있으면 activity 미합산, activity 단독이면 합산. 행은 표시 |
| 5 | Option A party_type 키 | **닫힘** — §5 COALESCE 통일로 해소(통계 SUM 도 COALESCE 사용 확정) |
| 6 | diag-golden | **닫힘** — 6분기 매핑 완료(§9 검증 항목 + §6-H/§6-I diag). enrichment·gender SUM 은 diag 0건이라 golden 무영향 |

**Phase 0 런타임 잔여 5건(모두 비블로커, 사전점검 단계로 정상 편입)**: ① party3 템플릿 content dump ② backfill 후 `date_from` 필터 activity 누락 1회 확인 ③ 운영상 객실행이 party_type 갖는 빈도(이중계상 발화 빈도) ④ `§4-2` 구현 grep 1회 ⑤ `§6-I` conditions_count 증가폭·split activity 발화 첫 관측.

> 그 외 `daily_host.py`/`daily_review.py`/`onsite_female_invite.py`/`party_hosts.py`/`cleancrew.py`(CLAUDE.md 미등재 신규 라우터)는 별도 모델 사용 + cleancrew 는 RoomAssignment INNER JOIN self-isolated 라 **activity 영향 없음 확인**.
