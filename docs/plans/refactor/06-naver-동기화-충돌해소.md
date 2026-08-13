# 네이버 동기화 ↔ 직원 수정 충돌 해소

> 작성 2026-08-06 · 상태: **설계 (구현 전)**
> 발단: ⑨ `core/reservation` 단위 리뷰

---

## 0. 한 줄

> **네이버가 아무것도 안 바꿨는데도 5분마다 덮어쓰기를 시도합니다.**
> 그래서 보호 플래그 7종이 생겼습니다.
> **안 바뀌었으면 안 건드리게** 하면 플래그가 존재할 이유의 대부분이 사라집니다.

---

## 1. 문제

```
09:00  네이버 인원 4명 · 우리 DB 4명
09:05  직원이 5명으로 수정
09:10  동기화 — 네이버는 여전히 4명 (아무것도 안 바뀜)
       → 그런데 "4명으로 덮어쓰기" 시도
       → 💥 직원 수정이 날아감
```

**네이버는 아무것도 안 바꿨는데 충돌이 났습니다.**

### 왜 자주 나는가 — 조회 창이 가장 바쁜 구간과 겹칩니다

```
5분 동기화가 가져오는 것 (real/reservation.sync_reservations)
  ① REGDATE 최근 1일    새 예약 / 취소
  ② USEDATE 오늘~내일   임박한 체크인 전부      ← 여기
```

**오늘·내일 손님 = 직원이 지금 배정하고 · 인원 확인하고 · 연장 처리하는 바로 그 예약들.**
그런데 그 예약들은 며칠~몇 주 전에 만들어져서 **네이버 쪽은 거의 안 바뀝니다.**

### 그래서 플래그가 7종으로 번식했습니다 (실측)

| 플래그 | 검사 | 설정 |
|--------|-----:|-----:|
| `manually_extended_until` | 18 | 7 |
| `gender_manual` | 14 | 0 |
| `manually_edited_fields` | 11 | 5 |
| `check_out_pinned` | 9 | 4 |
| `is_split_managed` | 7 | 0 |
| `stay_group_excluded` | 5 | 2 |
| `check_in_pinned` | 4 | 1 |
| **계** | **68** | **19** |

> 조사 문서 경고: *"보호 플래그 8종 — **값 목록이 있는 곳: 없음** — 코드 곳곳에 흩어져 있음 ⚠️"*

`_update_reservation`(265줄) 안에 **보호 방식이 8가지** 공존합니다.

---

## 2. 원인

```
지금:  네이버가 준 값으로 그냥 넣는다        →  네이버가 안 바뀌었어도 넣는다
                                              →  직원 수정과 충돌
                                              →  핀으로 막는다 (7종 · 68곳)
```

빠진 질문 하나: **"네이버 값이 실제로 바뀌긴 했나?"**

---

## 3. 해결 — 2단계

```
① 지문(Fingerprint)   공격을 멈춘다     ← 싸고 안전 · 통증 대부분 해소
② 핀 통합             방어를 정리한다   ← 7종 → 1종
                                          ①이 먼저라 이때 위험이 낮아짐
③ (나중 판단)          남은 케이스
```

### 왜 이 순서인가

| | 위험 | 효과 |
|---|---|---|
| **핀 통합 먼저** | 🟧 68곳을 고쳐야 함. 하나 빠뜨리면 보호가 풀려 **직원 수정이 날아감** | 코드 정리 (통증 그대로) |
| **지문 먼저** | 🟨 새 테이블 + `if` 하나. 기존 로직 무변경 | **통증 해소** |

그리고 지문이 먼저면 **핀 통합이 안전해집니다** — 대부분의 덮어쓰기가 이미 차단돼 있어,
통합 중 실수로 보호가 풀려도 실제 피해가 작습니다.

---

## 4. 1단계 — 지문

### 4-1. 무엇

```python
# services/naver_sync.py:236  (existing 분기 직전)
if existing:
    fp = fingerprint(res_data)
    if fp == stored_fingerprint(existing.id):
        skipped += 1
        continue                    # 네이버가 아무것도 안 바꿈 → 통째로 건너뜀
    _update_reservation(db, existing, res_data)
    save_fingerprint(existing.id, fp)
```

**끝입니다.**

### 4-2. 저장 — 새 **테이블** (컬럼 아님)

[G-5](./01-정리대장.md) 때문에 **컬럼 추가는 위험**합니다 (alembic 이 21종 중 8종만 앎).
그런데 ② `shared/storage` 리뷰에서 확인한 사실:

```
Base.metadata.create_all()  →  없는 "테이블"은 만듦 ✅  ·  있는 테이블에 "컬럼"은 못 넣음 ❌
```

실제로 `users` · `buildings` · `activity_logs` 등 **8개 테이블이 alembic 없이 create_all 로만 존재**합니다.

> **→ 새 테이블은 지금 안전합니다. G-5 를 기다릴 필요 없습니다.**

```python
class NaverSyncState(TenantMixin, Base):
    __tablename__ = "naver_sync_states"
    reservation_id = Column(Integer, ForeignKey("reservations.id"), unique=True, index=True)
    fingerprint    = Column(String(64))    # sha256 hex
    synced_at      = Column(DateTime)
    source         = Column(String(20))    # 'stable' | 'unstable'
```

### 4-3. ✅ 지문 계산 — **(나) 우리 가공 후 값 기준** (확정)

| 안 | 내용 | 판정 |
|----|------|------|
| (가) 네이버 원본만 | 상품명을 바꿔도 기존 예약에 반영 안 됨 | ❌ |
| **(나) enrichment 후 값** | 상품 설정 변경이 예약에 반영됨 | ✅ **채택** |

Phase 2 enrichment(상품명 · 인원 · 도미토리 판정 · section_hint)를 **거친 뒤**의
`res_data` 중 **우리가 실제로 쓰는 필드만** 골라 정렬 후 해시합니다.

```python
_FINGERPRINT_FIELDS = (          # 쓰기 대상 필드만. 우리 운영 필드는 제외
    "customer_name", "phone", "visitor_name", "visitor_phone",
    "date", "end_date", "time", "status",
    "people_count", "booking_count", "total_price",
    "naver_biz_item_id", "room_type", "biz_item_name",
    "booking_options", "custom_form_input",
    "gender", "age_group", "visit_count",
    "confirmed_at", "cancelled_at",
)

def fingerprint(res_data: dict) -> str:
    payload = {k: res_data.get(k) for k in _FINGERPRINT_FIELDS}
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
```

> ⚠️ **(나)의 대가**: `NaverBizItem.display_name` 이나 `default_capacity` 를 바꾸면
> 그 상품의 **모든 예약 지문이 한꺼번에 바뀌어** 다음 동기화에서 전부 재계산됩니다.
> **의도된 동작**이지만 한 번에 몰리므로, 상품 설정 대량 변경 시 인지 필요.

### 4-4. 무엇이 해결되나

| | |
|---|---|
| ✅ **"네이버가 안 바꿨는데 덮어쓰는" 케이스 전부 제거** | 통증의 대부분 |
| ✅ 5분마다 도는 쓰기 부하 감소 | 부수 효과 |
| ✅ `skipped` 카운트로 **실제 변경 빈도가 관측됨** | 2단계·3단계 판단 근거 |
| ❌ 네이버가 필드 A 를 바꿨는데 직원이 필드 B 를 고친 경우 | B 가 날아감 → **핀이 계속 막아줌** (그래서 ②가 필요) |

### 4-5. 위험

| # | 위험 | 대비 |
|---|------|------|
| **W1** | 첫 동기화 때 지문 없음 | 지문 없으면 **기존대로 업데이트 + 지문 저장**. 다음부터 정상 |
| **W2** | 지문이 같은데 실제로는 달랐던 경우(해시 충돌 등) | sha256 — 실질 0. 단 `_FINGERPRINT_FIELDS` 에서 **빠뜨린 필드는 영원히 반영 안 됨** → 목록 검토 필수 |
| **W3** | 우리 운영 필드가 지문에 섞이면 | `section` · `party_type` · 배정 등은 **제외** (네이버가 안 주는 값) |
| **W4** | 상품 설정 변경 시 대량 재계산 | §4-3 각주. 필요하면 배치 분산 |
| **W5** | 언스테이블(제2 계정) | `source` 컬럼으로 분리 |

---

## 5. 2단계 — 핀 통합

지문이 대부분을 막은 **뒤에** 진행합니다.

### 목표

```
플래그 7종 · 검사 68곳
        ↓
is_pinned(reservation, field)  하나
```

### 유지 / 통합

| 플래그 | 처리 |
|--------|------|
| `check_in_pinned` · `check_out_pinned` | → `manually_edited_fields` 로 흡수<br>(`reservation_mutator.py:160` 에 **"PR2 에서 통합 예정"** 이미 명시) |
| `gender_manual` · `is_split_managed` | → 같은 dict 로 흡수 |
| `manually_extended_until` | **유지** — 보호 기능만 제거, **UI 표시용**("연박 취소" 버튼 조건)으로만 |
| `stay_group_excluded` | **유지** — 네이버와 무관한 **운영 데이터** |

### ⭐ 이 단계는 **이미 계획서가 있습니다** — 새로 쓰지 말 것

| 문서 | 내용 | 상태 |
|------|------|------|
| [`mutator-step-15a-naver-guard-consolidation.md`](../mutator-step-15a-naver-guard-consolidation.md) | `naver_sync` 의 `manually_extended_until` OR 가드 제거 → `check_out_pinned` 단독 보호 (**~7줄**) | 방안 확정 |
| [`mutator-step-15-manually-extended-until-deprecation.md`](../mutator-step-15-manually-extended-until-deprecation.md) | 필드 완전 제거 | ⏸ **보류** — 프론트 `RoomAssignment.tsx:546` 이 사용 중 |
| [`mutator-migration-plan.md`](../mutator-migration-plan.md) §F | 부모 계획 | 진행 중 |

**그리고 결론이 제 분석과 같습니다:**

> `manually_extended_until` = **"수동 연박이었음" 운영 표시** (UI 버튼 + 취소 진입 조건)
> `check_out_pinned` = **"사용자가 수동 변경" 동기화 보호**
> → **통합 불가. 의미 분리 유지하면서 backend 가드만 정리.**

사용자 확인(2026-05-15)까지 기록돼 있습니다:
> *"수동연박은 서비스로 1박 추가하는 케이스. … 나중에 수동 추가인지 실제예약인지 헷갈릴 수 있어 별도 표시함."*

> ⚠️ **§5-2 의 "3종류 분류"를 새로 하지 마세요.** `manually_extended_until` 에 대해서는
> **이미 끝나 있습니다** (①보호=제거 / ②UI표시=유지 / ③정합성=유지).
> 나머지 6종에 대해서만 같은 분류를 하면 됩니다.

### ⚠️ 먼저 분류해야 합니다

68곳이 전부 같은 질문이 아닙니다. `manually_extended_until` 18곳을 확인하니 3종류였습니다:

```
① 보호 판정    "네이버가 덮어써도 되나"       → is_pinned() 로 통합  ✅
② UI 표시      "연박취소 버튼을 보여줄까"      → 통합 대상 아님       🟡
③ 정합성 유지  "체크아웃보다 크면 클리어"       → 통합 대상 아님       🟡
```

> `section_registry` docstring 이 경고한 함정과 같습니다 — *"명세서로 옮기면 방어 로직을 잃는다"*.

---

## 6. 나중 판단 (지금 결정 안 함)

지문 + 핀 통합 뒤에도 남는 것을 **그때 데이터로** 판단합니다.

| 후보 | 내용 |
|------|------|
| 필드 단위 비교 | 네이버가 필드 A 를 바꿨을 때 직원이 고친 B 를 보존 |
| **"같은 사실 / 다른 사실" 재분류** | 인원 · 체크아웃 · 상태는 *네이버 예약값* 과 *현장 실제값* 이 **서로 다른 참인 사실** — 애초에 같은 칸에 넣은 게 원인일 수 있음 |
| 칸 분리 (`booked_*` / `actual_*`) | 충돌이 구조적으로 불가능해지나 **읽기 경로 100+곳** 변경 |

> 🔑 `manually_extended_until` 이 플래그가 아니라 **날짜 값**을 저장하고 있습니다.
> 코드가 이미 "칸 분리" 방향으로 절반 가다 만 흔적입니다.

**1단계의 `skipped` 카운트와 실제 변경 빈도가 나온 뒤에 판단합니다.** 지금 정하지 않습니다.

---

## 7. 단계

| # | 내용 | 위험 | 선행 |
|---|------|------|------|
| **N1** | `_FINGERPRINT_FIELDS` 목록 확정 (빠뜨리면 영원히 반영 안 됨) | 🟨 **검토 필수** | — |
| **N2** | `NaverSyncState` 테이블 신설 (`create_all` 자동) | 🟨 없음 | — |
| **N3** | 지문 기록만 — **건너뛰기는 아직 안 함** | 🟨 없음 | N2 |
| **N4** | 관측 — `skipped` 가 될 비율을 diag 로 기록 | 🟨 없음 | N3 |
| **N5** | 건너뛰기 활성화 | 🟧 | N4 |
| **N6** | 핀 분류 (보호 / UI / 정합성) — **`manually_extended_until` 은 이미 완료**, 나머지 6종만 | 🟨 | N5 |
| **N7** | [`mutator-step-15a`](../mutator-step-15a-naver-guard-consolidation.md) 실행 (~7줄) | 🟨 | N6 |
| **N8** | 핀 통합 → `is_pinned()` | 🟧 | N7 |
| **N9** | 플래그 정리 | 🟧 | N8 |

**N3~N4 가 안전장치입니다.** 건너뛰기를 켜기 전에 *"실제로 몇 %가 건너뛰어질지"* 를 먼저 봅니다.
숫자가 낮으면(= 네이버가 자주 바뀜) 전제가 틀린 것이므로 설계를 재검토합니다.

---

## 8. 결정 기록

| # | 질문 | 결정 |
|---|------|------|
| **Q31** | 핀 통합이 근본 해결책인가? | ❌ **방어 정리일 뿐.** 덮어쓰기 시도 자체는 계속됨 |
| **Q32** | 그럼 무엇이 먼저인가? | ✅ **지문 → 핀 통합.** 지문이 싸고 안전하며 통증을 실제로 없앰 |
| **Q33** | 지문 저장 위치? | ✅ **새 테이블 `naver_sync_states`** — 컬럼 추가는 G-5 로 막혔으나 테이블은 `create_all` 이 자동 생성 |
| **Q34** | 지문 계산 기준? | ✅ **(나) enrichment 후 값** — 상품 설정 변경이 반영돼야 정상 |
| **Q35** | 3-way merge · A/B/C 분리 · 칸 분리는? | ⏸ **보류** — 1·2단계 후 관측 데이터로 판단 (§6) |
