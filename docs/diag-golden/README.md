# Diag Golden Traces

> "이 동작은 어떤 이벤트들이 이 순서로 찍혀야 정답이다" 를 문서로 박아둔 곳.

매일 `ooo-log-validation` 스킬이 이 폴더를 기준으로 실운영 로그와 비교·검증한다.

## 구조

```
docs/diag-golden/
├── README.md            # 이 문서 (방법론)
├── invariants.md        # 항상 성립해야 하는 불변식 규칙
├── state.json           # 마지막 검증 체크포인트 (자동 갱신)
└── actions/             # 정답 trace YAML 파일들 (액션당 1개)
    ├── drag-single-night-past.yaml
    ├── drag-multi-night-past-cascade.yaml
    ├── schedule-execute-no-targets.yaml
    └── ...
```

## 정규화 룰 (필수)

원본 로그 라인을 비교 가능한 형태로 변환한다. **직접 텍스트 diff 는 절대 쓰지 않는다** (타이밍/ID 때문에 100% 실패).

### 삭제 (매번 달라짐)
| 필드 | 예시 |
|------|------|
| 타임스탬프 | `2026-04-21 13:29:44,706` |
| `req_id` 값 | `hi5n53mh` (유지는 하되 비교 제외) |
| `tid` 값 | `tid=2` |
| 숫자 식별자 | `res_id=4077`, `room_id=27`, `group_id=UUID` |
| `action` 세부값 | `action=drag_guest_to_room:res=4077,room=B308` → prefix 만 유지 (`drag_guest_to_room`) |
| 응답시간 | `ms=559` |
| 구체 날짜 값 | `original_from=2026-04-20`, `clamped_to=2026-04-21` |

### 상대화 (절대 날짜 → 상대 표현)

오늘(today)을 기준으로 상대 날짜로 변환한다:

| 원본 (today=2026-04-21 기준) | 정규화 |
|------------------------------|--------|
| `from_date=2026-04-20` | `from_date=today-1` |
| `from_date=2026-04-21` | `from_date=today` |
| `from_date=2026-04-22` | `from_date=today+1` |
| `end_date=2026-04-21` | `end_date=today` |

### 보존 (고정값, 비교 대상)
| 종류 | 예시 |
|------|------|
| 이벤트 이름 | `[assign_room.enter]` |
| bool/enum | `is_dorm=True`, `assigned_by=manual`, `outcome=no_targets` |
| 카운트/상태 | `dates_count=1`, `created=1`, `pushed_count=0`, `status=200` |
| `action` prefix | `drag_guest_to_room`, `undo_assign`, `auto_assign_button` |

## 이벤트 카테고리 (비교 규칙)

| 카테고리 | 의미 | 위반 시 |
|---------|------|---------|
| `MANDATORY` | 이 순서로 반드시 존재, 필드값도 일치 | DIFF (회귀 의심) |
| `VARIABLE_COUNT` | 존재 여부만 (min 이상) | DIFF |
| `CONDITIONAL` | 전제 조건 만족 시에만 출현 | 조건부 DIFF |
| `FORBIDDEN` | 이 플로우에서 절대 나오면 안 됨 | HIGH 에러 |

## YAML 스키마 (액션 정답지)

```yaml
action: <사람이 읽을 액션 이름>
description: |
  액션의 의미와 전제 조건을 설명
reference_commit: <YAML 작성 시점의 커밋 SHA>
reference_case: <수집한 원본 로그 req_id + 날짜>
created_at: <YYYY-MM-DD>

preconditions:
  # 이 trace 가 나오려면 만족해야 하는 조건
  reservation:
    is_long_stay: <bool>
    check_in: <상대 날짜>
    check_out: <상대 날짜>
  user_action: <드래그, 버튼, 모달 선택 등>
  modal_choice: <해당 시>

expected_trace:
  # 이벤트 시퀀스 (순서대로)
  - event: <이벤트 이름>
    category: MANDATORY | VARIABLE_COUNT | CONDITIONAL
    fields:
      <필드>: <기댓값 or '*' 로 와일드카드>
    # VARIABLE_COUNT 인 경우
    min: <최소 발생 횟수>
    # CONDITIONAL 인 경우
    when: <자연어 조건>

forbidden_events:
  # 이 trace 에서는 절대 나오면 안 되는 이벤트들
  - <이벤트 이름>: <이유>
```

## 정답지 추가/수정 워크플로우

### 추가 (새 플로우 발견 시)
1. `ooo-log-validation` 스킬이 NO_MATCH 로 판정한 trace 발견
2. 정규화 룰 적용해 YAML 초안 생성
3. **사용자 승인 필수** (근거: 원본 로그 스니펫 + 코드 레퍼런스)
4. 승인 후 `actions/` 에 커밋

### 수정 (기존 플로우가 의도적으로 변경됨)
1. 코드 수정 시 해당 정답지도 **같은 PR 안에서** 수정
2. 커밋 메시지에 "golden: <file>.yaml 업데이트 — <이유>" 명시
3. 수정 안 하고 배포 → 다음 검증에서 DIFF 로 잡힘 → 스킬이 "의도된 변경인지?" 질문

## 안티패턴 ❌

- **PR 리뷰 없이 golden 자동 갱신** — 회귀 감지 기능이 사망함
- **원본 로그 그대로 저장** — 타이밍/ID 때문에 영구히 DIFF 만 나옴
- **모든 이벤트를 MANDATORY 로 지정** — filter.applied 같은 반복 이벤트는 VARIABLE_COUNT
- **한 파일에 여러 액션 넣기** — 매칭 알고리즘이 혼란
