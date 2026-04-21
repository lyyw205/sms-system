# Diag Invariants

> 어떤 동작이든 **무조건 성립해야 하는** 불변 규칙들. Golden trace 가 "이 액션은 이렇게 흘러야 한다" 라면, 불변식은 "그 외 어떤 경우에도 이건 절대 깨지면 안 된다" 이다.

스크립트 `scripts/diag/check_invariants.py` 가 이 파일의 규칙들을 파싱해 로그에 대해 검증한다.

## INV-1: request enter/exit 짝 맞음
**규칙**: 모든 `[request.enter]` 는 동일 `req_id` 의 `[request.exit]` 또는 `[request.error]` 가 뒤따라야 한다.

**검사 방법**:
- `req_id` 로 그룹핑
- 각 그룹 내 `request.enter` 건수 == `request.exit` + `request.error` 건수

**위반 시**: 요청이 중간에 중단됨 — 미들웨어 에러나 예외 누수 가능성. HIGH.

---

## INV-2: assign_room enter/exit 짝 맞음
**규칙**: 모든 `[assign_room.enter]` 는 동일 `req_id` + 동일 `res_id` 의 `[assign_room.exit]` 로 닫혀야 한다.

**위반 시**: 서비스 내부 예외 또는 rollback 후 exit 누락. HIGH.

---

## INV-3: schedule.execute outcome 필드 필수
**규칙**: 모든 `[schedule.execute.exit]` 는 `outcome=` 필드를 가져야 하고, 값은 다음 중 하나:
- `completed`, `schedule_not_found`, `template_not_found`, `send_condition_not_met`, `no_targets`, `exception`

**위반 시**: `3055009` 커밋의 계측 갭 메우기 로직 회귀.

---

## INV-4: cascade clamp 가드 조건 준수
**규칙**: `[cascade.clamped_to_today]` 이벤트가 찍혔다면, 직전의 해당 예약 상태가 다음을 **전부 만족**해야 한다:
- `is_long_stay=true` (연박자)
- `apply_subsequent=true` (cascade 모드)
- `original_from < today` (과거 드롭)

단박자(`is_long_stay=false`) 에 이 이벤트가 찍히면 **가드 로직 회귀**.

**검사 방법**: 이벤트의 `original_from` 과 `clamped_to` 값을 비교, 그리고 같은 `req_id` 의 `assign_room.enter` 에서 `is_dorm` 필드 등으로 예약 특성 추정 (정확도 낮음). 실시간 검증보다는 **의심 사례 목록** 출력에 쓰기.

**위반 시**: MEDIUM (확정 전 사람 판단 필요).

---

## INV-5: 금지된 이벤트 출현 없음
**규칙**: 다음 이벤트들은 현재 코드상 **절대 찍힐 수 없어야** 한다 (과거 커밋에서 제거됨):

- `cascade.full_past_noop` — `0ec7084` 에서 제거
- `cascade.downgraded_to_single` — `0ec7084` 에서 제거
- `cascade.group_member_clamped` — `0ec7084` 에서 제거
- `cascade.group_member_skipped` — `0ec7084` 에서 제거
- `past_drop.blocked` — `863f2fe` 에서 제거

**검사 방법**: 단순 grep. 존재하면 회귀.

**위반 시**: HIGH (누군가 롤백/재도입한 것).

**주의**: 이 목록은 커밋 시점에 맞춰 **유지보수 필요**. 새로운 "사망한 이벤트" 가 생기면 여기 추가.

---

## INV-6: /health 노이즈 없음
**규칙**: `[request.enter]` 이벤트 중 `path=/health` 가 나타나면 안 됨 (미들웨어에서 스킵해야 함).

**위반 시**: `3055009` 의 /health skip 로직 회귀. MEDIUM.

---

## INV-7: naver_sync 카운트 일관성
**규칙**: `[naver_sync.exit]` 의 `synced` 은 `added + updated` 와 일치해야 한다 (취소/스킵 제외한 정규 흐름).

**검사 방법**: 각 `naver_sync.exit` 행의 `synced`, `added`, `updated` 값 추출 비교.

**위반 시**: 동기화 로직 회귀. MEDIUM.

---

## INV-8: 민감정보 마스킹 확인
**규칙**: 로그 전체에서 **마스킹 안 된 전화번호/이메일** 패턴이 나오면 안 된다.
- 010-dddd-dddd 완전 노출 금지 (`010\d{4,}\d{4}` 정규식으로 마스킹 빠진 번호 탐지)
- 이메일 @ 원본 노출 금지

**위반 시**: PII 누수. HIGH (즉시 보고).

---

## 적용 우선순위

| 규칙 | Severity | 수동 확인 필요 |
|------|----------|----------------|
| INV-1 | HIGH | No (자동) |
| INV-2 | HIGH | No |
| INV-3 | MEDIUM | No |
| INV-4 | MEDIUM | Yes (거짓양성 가능) |
| INV-5 | HIGH | No |
| INV-6 | MEDIUM | No |
| INV-7 | MEDIUM | No |
| INV-8 | HIGH | No |

## 새 불변식 추가 방법

1. 이 파일에 `## INV-N: 제목` 섹션으로 추가
2. 규칙/검사방법/위반영향 3개 필드 필수 기입
3. `scripts/diag/check_invariants.py` 에 실제 검증 로직 추가
4. 같은 PR 에 테스트 케이스 포함 (위반 예시 로그로)
