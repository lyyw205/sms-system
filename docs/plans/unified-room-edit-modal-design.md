# 통합 "객실 정보 변경" 모달 — UI/IA 설계 초안

> 상태: **⚠️ 폐기(SUPERSEDED) — 아래 §0~6은 채택되지 않은 무거운 단일스크롤 모달 설계.** 실제 구현은 사용자 요청에 따라 **5단계 순차 위저드**(`frontend/src/pages/Quick/UnifiedRoomEditModal.tsx`)로 대체됨. 이 문서는 설계 검토 기록으로만 보존.
> 작성 2026-06-11
> 목적: 더블룸→트윈룸처럼 객실 정보를 바꿀 때 **4개 모달 + 2개 페이지**를 오가던 흐름을, **이동 없는 단일 모달**로 통합.
> 제약: **기존 백엔드/프론트엔드는 그대로 둔다.** 새 모달 컴포넌트 1개를 독립 추가하고, **기존 엔드포인트만 오케스트레이션**한다.

---

## 0. 핵심 전제 (왜 "객실+상품" 통합인가)

다운스트림(할증·무료업그레이드·섹션 배정)은 **객실의 링크가 아니라, 손님이 예약한 상품 `reservation.naver_biz_item_id`(=`NaverBizItem`)** 를 읽는다.
갓 동기화된 트윈 상품은 `grade=NULL / default_capacity=1 / section_hint=NULL` 이라:
- `grade=NULL` → 업그레이드 약속/객후 칩이 **조용히 멈춤**
- `default_capacity=1` → 인원초과 할증 **과청구**
- `section_hint=NULL` → 신규 예약이 **'미배정' 섹션**으로 추락

→ 따라서 통합 모달은 **객실(Room)** 과 **연결 상품(NaverBizItem)** 을 같은 화면에 동거시켜, 상품 메타 누락을 구조적으로 막는다.

---

## 1. 오케스트레이션 청사진 (백엔드 무수정 · 엔드포인트 4개)

| # | 엔드포인트 | 담는 필드 | 권한 | 비고 |
|---|-----------|----------|------|------|
| ① | `PUT /api/rooms/{id}` | `room_type`, `base/max_capacity`, `dormitory`, `bed_capacity`, `building_id`, `door_password`, `room_memo`, **`biz_item_links[]`(우선순위 포함, FULL set)** | STAFF | 응답 `{room, warning, affected_reservation_ids}` |
| ② | `PATCH /api/rooms/naver/biz-items` | `[{biz_item_id, grade, default_capacity, section_hint, default_party_type, display_name}]` | STAFF | **다른 테이블** · `None`=무변경 · grade 변경 시 칩 reconcile |
| ③ | `PATCH /api/rooms/grades` | `[{id, grade}]` (객실 등급) | **ADMIN** | `RoomUpdate`에 grade 없어 분리 필수 · 칩 reconcile |
| ④ | `POST /api/rooms/reorder` | `{ordered_ids:[전체 객실]}` | **ADMIN** | whole-set · 부분 전송=400 |

**Prefill 읽기** (모달 오픈 시): `GET /api/rooms` (객실+`biz_item_links_detail`+grade+sort_order+memo) · `GET /api/rooms/naver/biz-items` (상품 picker + 상품 메타).

> ⚠️ **크로스-엔드포인트 트랜잭션 없음.** ①이 커밋된 뒤 ③이 403날 수 있음 → 절대 "전부 성공" 환상을 주지 말고 **호출별 결과**를 보고한다.

---

## 2. 최종 IA — 단일 세로 스크롤 + 상단 sticky "전환 체크" strip

```
┌─ 객실 통합 편집 · A203 ───────────────────────────[size=2xl]──[✕]─┐
│ ▸ 더블→트윈 전환 체크 (sticky)                                      │  ← 항상 보임. 저장 후 "실측" 상태 반영
│   ① 정원 ≥2 ●   ② 객실등급=3 ●   ③ 상품등급=3 ○   ④ 상품정원2·room ○ │     (●=충족 / ○=미충족=회색)
├────────────────────────────────────────────────────────────────────┤
│ (선택) 빠른 전환 프리셋  [ 3 · 트윈 ▾ ]  → 아래 값들을 제안 채움(잠금X)│  ← C 이식: 채우되 잠그지 않음
│                                                                      │
│ ┌─ ① 객실 기본 ─────────────────────────── PUT /rooms/{id} (STAFF) ┐│
│ │ 건물 [본관 ▾]   객실번호 [A203*]   객실타입 [트윈룸*] ← (더블룸)   ││
│ │ 기준정원 [2]  최대정원 [3]   도미토리(⚪off)  베드[1](도미시)      ││
│ │ 문비번 [1234*]   메모 [더블→트윈 전환 2026-06-11        ]         ││
│ │ ┌ ⚠ 미래 배정 3건 영향 — 수동 재배정 검토 ────────────────────┐ ││  ← PUT 응답 affected
│ │ │   [tid=1] res=6201, 6233, 6290 · 정원/링크 변경 감지          │ ││     (테넌트 그룹핑 규약)
│ │ └──────────────────────────────────────────────────────────────┘ ││
│ └──────────────────────────────────────────────────────────────────┘│
│ ┌─ ② 연결 상품 + 배정순위 ──────────────── PUT /rooms/{id} (STAFF) ┐│
│ │ [✓트윈룸(info)] [더블룸] [도미4인]   ← 토글칩 (현재 FULL set)      ││
│ │ 선택됨: 트윈룸   남우선[1]  여우선[1]                              ││
│ │ ℹ 해제한 칩의 링크는 삭제됩니다 (전체 집합 전송)                   ││  ← FULL-set 경고
│ └──────────────────────────────────────────────────────────────────┘│
│ ┌─ ③ 등급 비교 ───────── PATCH /grades(ADMIN) + /biz-items(STAFF) ─┐│
│ │   객실 등급          관계              상품 등급                   ││
│ │  [3 트윈 ▾]    ▶  3 > ? 성립불가  ◀   [● 미설정 ▾]🔴             ││  ← 부등호 배지 = 업그레이드 규칙
│ │  (ADMIN)                                  (STAFF)                 ││     "배정등급 > 상품등급 → 발송"
│ │  1=도미 < 2=더블 < 3=트윈 < 4=트윈3인 < 5=스위트                  ││
│ └──────────────────────────────────────────────────────────────────┘│
│ ┌─ ④ 연결 상품 메타 (트윈룸) ──────────── PATCH /biz-items (STAFF) ┐│
│ │ 기준정원 [1]🔴 → [2]    섹션 [없음]🔴 → [room ▾]                  ││  ← C 이식: Before→After diff
│ │ 표시명 [트윈룸    ]     파티타입 [없음 ▾]                          ││     (🔴 = 갓 동기화 미설정값)
│ │ ⓘ 빈칸 = 변경 안 함 (None=no-change, NULL로 되돌리기 불가)         ││
│ └──────────────────────────────────────────────────────────────────┘│
│ ┌─ ⑤ 순서 (ADMIN, 접힘 기본) ───────────── POST /reorder ──────────┐│
│ │ … A201 / A202 / ▶A203◀ [▲][▼] / A204 …  (전체 순서 통째 전송)     ││
│ └──────────────────────────────────────────────────────────────────┘│
│ ┌─ 영향 / 경고 (저장 버튼 바로 위, 심각도순) ──────────────────────┐│  ← C 이식: 심각도 랭킹
│ │ ⛔ 기존 예약 비소급 — 링크/메타 변경은 향후 동기화 예약에만 적용  ││  [#F04452]
│ │ ⛔ 상품 등급/정원 미설정 시 업그레이드 무발송·할증 과청구          ││  [#F04452]
│ │ ⚠ 등급/정원 변경 → 업그레이드·인원초과 칩 재계산                  ││  [#FF9F00]
│ └──────────────────────────────────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────────┤
│ 결과: ①② 저장됨 · 상품 저장됨 · 객실등급 ⛔403(관리자)               │  ← 호출별 결과칩
│                                         [취소(light)] [저장(blue)]   │  ← 저장 중 Spinner
└────────────────────────────────────────────────────────────────────┘
```

### 섹션 요약
| 섹션 | 엔티티 | 엔드포인트 | 권한 | 핵심 |
|------|--------|-----------|------|------|
| sticky 전환 체크 strip | — | (읽기) | — | 4조건 점등 = 누락 방지 핵심. **저장 후 실측 상태**로 갱신 |
| (선택) 빠른 전환 프리셋 | — | (UI만) | — | 등급 1~5 선택 → 캐스케이드 **제안 채움(잠금X)** |
| ① 객실 기본 | Room | ① PUT | STAFF | 기존 size=md 객실수정 모달 흡수 |
| ② 연결 상품 + 배정순위 | RoomBizItemLink | ① PUT(동일 호출) | STAFF | 별도 '배정 순서' 모달 흡수 · **FULL set** |
| ③ 등급 비교 | Room + NaverBizItem | ③ + ② | 좌 ADMIN / 우 STAFF | 부등호 배지로 규칙 시각화 |
| ④ 상품 메타 | NaverBizItem | ② PATCH | STAFF | Before→After diff · 🔴 미설정 |
| ⑤ 순서 | Room | ④ reorder | ADMIN | 접힘 기본 · whole-set |
| 영향/경고 패널 | — | (읽기) | — | 비소급/미설정=Error, 칩재계산=Warning |

---

## 3. 저장 오케스트레이션 (순차 await · per-call 보고)

기존 `saveBuildingsMutation` 패턴 재사용 (검증된 in-repo orchestration).

```
저장 클릭
 0) 사전검증: room_number/room_type 공란 → toast 후 중단
 0.5) [데이터손실 가드] biz_item_links 를 GET 으로 재페치 → 오픈 시 스냅샷과 diff.
      드리프트 감지 시 "다른 곳에서 링크가 바뀌었습니다, 새로고침" 경고 후 중단
 1) dirty diff: 카드별 prefill 스냅샷 대비 변경 카드만 호출 큐 적재
 2) [soft confirm] 상품 grade=NULL / default_capacity=1 / section_hint=NULL 인데 저장하려 하면
      "상품 등급/정원이 미설정입니다 — 그래도 저장할까요?" 확인
 3) ─ Phase 1 ─ [STAFF] PUT /api/rooms/{id}      ①+② (room + links FULL set)
       → 응답 warning/affected_reservation_ids 를 ① 하단 배너로 (실패해도 모달 유지)
 4) ─ Phase 2 ─ [STAFF] PATCH /naver/biz-items   ③우측 상품grade + ④ 메타 (변경 키만, None=무변경)
 5) ─ Phase 3 ─ [ADMIN] PATCH /rooms/grades       ③좌측 객실grade  (STAFF면 스킵, 403이면 per-call 경고)
 6) ─ Phase 4 ─ [ADMIN] POST /rooms/reorder       ⑤ (변경 시만, 전체 ordered_ids)
 7) 각 Phase try/catch → {phase: ok|fail|skipped, msg} 누적 → 결과칩 + 토스트로 정직 보고
 8) onSettled: qc.invalidateQueries(rooms.all + rooms.bizItems + buildings.list + reservations.all)
 9) 전부 성공+경고없음 → 모달 닫기 / 일부 실패·warning → 모달 유지(재시도·affected 확인)
 10) sticky strip 을 **저장 후 실측값**으로 재계산 (pre-save 의도가 아니라 post-save 상태)
```

---

## 4. 필수 구현 가드 (리스크 → 가드)

| 리스크 | 가드 |
|--------|------|
| **모달 폭** — 커스텀 `Modal lg = 512px`로 좁아 ③ 좌우 비교가 깨짐 | `size="2xl"` 또는 `"3xl"` 사용 (lg 금지) |
| **FULL-set 링크 데이터손실** — 안 보낸 링크는 백엔드가 삭제(`_sync_biz_item_links`) | 전체 `biz_item_links_detail` prefill → **저장 직전 재페치+diff**, 드리프트 시 중단 |
| **크로스 트랜잭션 없음** — 반쪽 전환(객실=트윈인데 상품 grade=NULL) | per-call 결과칩 + sticky strip을 **post-save 실측**으로 |
| **None=무변경** — 잘못 넣은 값을 NULL로 못 되돌림 | "빈칸=변경 안 함" 캡션 명시 |
| **클라 권한 게이팅은 신규** — RoomSettings는 현재 role 안 읽음 | 백엔드 403이 최종 방어선 · 사전 게이팅해도 **403 graceful 처리** 필수 |
| **상품 PATCH엔 서버 warning 없음** — 운영자가 "경고 없으니 안전"으로 오해 | 상품 카드의 🔴 미설정 표식은 **클라가 따로 계산** |

---

## 5. 결정 필요 / 미해결

1. **빠른 전환 프리셋 채택 여부** — C의 등급 preset 자동채움은 이동을 가장 줄이지만(심사 nav 5점), 무비판 수용 위험. → "채우되 잠금X + Before→After diff 강제 노출"로 완화안 반영. **포함할지 결정 필요.**
2. **⑤ 순서(reorder) 포함 여부** — 단일 객실 편집과 whole-set 정렬은 멘탈모델이 다름. C는 모달에서 **제외**(테이블 DnD가 담당) 주장. B는 접힘 포함. → 기본 "접힘 포함", 합의 시 제외 가능.
3. **진입점** — 어디서 이 모달을 여는가? (RoomSettings 행 '통합편집' 버튼 / RoomAssignment 호수 우클릭 등)
4. **soft-block 강도** — 상품 메타 미설정 시 soft confirm만? 아니면 저장 버튼 비활성?

---

## 6. 구현 범위 (백엔드 무수정 전제)

- **새 파일**: `frontend/src/pages/RoomSettings/UnifiedRoomEditModal.tsx` (또는 components 하위) 1개.
- **재사용 API**: `roomsAPI.update / updateBizItems / updateRoomGrades / reorder / getAll / getBizItems` (이미 전부 존재).
- **재사용 패턴**: 토글칩(color=info), grade `<Select 1~5>`, `.section-card`, `saveBuildingsMutation` 오케스트레이션, 다크모드 토큰.
- **기존 4모달/2페이지**: 그대로 둠 (이 모달은 독립 추가, 기존 흐름과 공존).

---

### 부록 — 심사 결과 (judge panel)
- 베이스: **B 단일 스크롤** (운영속도·안전성 심사 1위 / 디자인·구현 2위)
- 이식: A의 sticky 전환 체크 strip·등급 cross-lighting / C의 Before→After diff·심각도 영향패널
- A 탭형: 디자인 적합 1위지만 "전체 한눈" 약함 · C 가이드형: 명료성 최고지만 구현비용·auto-fill 리스크
