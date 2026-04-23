# consecutive_stay.py 수정 제안

이 문서는 `backend/app/services/consecutive_stay.py`를 기준으로, 현재 코드에서 수정하면 좋은 부분과 충돌이 우려되는 부분을 정리한 내용입니다.

## 핵심 요약

이 파일은 따로 들어온 예약들을 하나의 연박 그룹으로 묶는 역할을 합니다.

예를 들어 아래처럼 따로 저장된 예약이 있을 때:

```text
예약 A: 김철수 / 4월 1일 체크인 / 4월 2일 체크아웃
예약 B: 김철수 / 4월 2일 체크인 / 4월 3일 체크아웃
```

시스템은 이 두 예약을 같은 사람의 이어진 예약으로 보고 같은 `stay_group_id`로 묶습니다.

이 값은 단순 화면 표시용이 아닙니다. 아래 기능에도 영향을 줍니다.

- 객실 배정
- 같은 방 유지 로직
- SMS 발송 대상
- 첫날/마지막날 메시지 판단
- 연박자 제외 필터

그래서 잘못 묶이면 객실 안내나 SMS 발송까지 같이 틀어질 수 있습니다.

## 1. link_reservations()에 백엔드 검증이 부족함

위치: `backend/app/services/consecutive_stay.py`

`link_reservations()`는 사용자가 직접 여러 예약을 연박 그룹으로 묶을 때 호출됩니다.

현재 문제는 함수 자체가 날짜 연속성을 검사하지 않는다는 점입니다.

예를 들어 API를 직접 호출하면 아래처럼 말이 안 되는 예약도 묶일 수 있습니다.

```text
예약 A: 김철수 / 4월 1일 ~ 4월 2일
예약 B: 이영희 / 4월 10일 ~ 4월 11일
```

프론트 모달에서는 날짜가 이어지는지 검사하지만, 백엔드 함수는 받은 ID들을 그대로 묶습니다.

수정 제안:

- 예약이 2개 이상인지 확인
- 모두 같은 tenant인지 확인
- 모두 `CONFIRMED` 상태인지 확인
- `이전 예약.check_out_date == 다음 예약.check_in_date`인지 확인
- 날짜가 이어지지 않으면 API에서 400 에러 반환

우선순위: 높음

## 2. 기존 연박 그룹끼리 섞일 때 충돌 가능성이 있음

위치: `backend/app/services/consecutive_stay.py`

현재 `link_reservations()`는 선택된 예약 중 하나라도 기존 `stay_group_id`가 있으면 그 값을 재사용합니다.

문제는 서로 다른 그룹에 속한 예약을 같이 묶는 경우입니다.

예시:

```text
기존 그룹 A: 예약 1, 예약 2
기존 그룹 B: 예약 3, 예약 4

사용자가 예약 2, 예약 3을 새로 묶음
```

현재 로직에서는 먼저 발견된 그룹 ID를 재사용할 수 있습니다. 그러면 기존 그룹 A/B의 일부 예약만 빠지거나, 남은 예약의 순서가 꼬일 수 있습니다.

수정 제안:

- 서로 다른 `stay_group_id`가 섞이면 400 에러 반환
- 또는 묶기 전에 기존 그룹을 명시적으로 해제한 뒤 새 그룹 생성

개인적으로는 첫 번째 방식이 더 안전합니다.

```text
서로 다른 기존 연박 그룹을 한 번에 묶을 수 없습니다.
먼저 연박 그룹을 해제한 뒤 다시 묶어주세요.
```

우선순위: 높음

## 3. visitor_phone만 있는 예약이 자동 감지에서 빠질 수 있음

위치: `backend/app/services/consecutive_stay.py`

자동 감지 함수 `detect_and_link_consecutive_stays()`는 예약을 조회할 때 현재 `phone`이 있는 예약만 가져옵니다.

현재 조회 조건은 대략 이런 의미입니다.

```text
phone이 null이 아니고
phone이 빈 문자열이 아닌 예약만 조회
```

그런데 실제 매칭 로직에서는 `visitor_phone`도 사용합니다.

즉, 의도는 방문자 전화번호도 매칭에 쓰는 것인데, 예약자 전화번호 `phone`이 비어 있으면 애초에 조회 대상에서 빠질 수 있습니다.

문제 예시:

```text
예약 A: customer_name=김철수, phone=빈값, visitor_phone=010-1111
예약 B: customer_name=김철수, phone=010-1111
```

이론상 같은 사람으로 묶을 수 있어야 하지만, 예약 A가 조회에서 제외될 수 있습니다.

수정 제안:

- `phone` 또는 `visitor_phone` 중 하나라도 있으면 자동 감지 대상에 포함

우선순위: 중간

## 4. 날짜가 문자열이라 비교와 정렬이 취약함

위치: `backend/app/services/consecutive_stay.py`

현재 예약 날짜는 문자열입니다.

정상 형식이 항상 `YYYY-MM-DD`라면 문자열 비교도 대부분 문제 없습니다.

하지만 날짜 형식이 깨지면 정렬과 비교가 이상해질 수 있습니다.

예시:

```text
2026-04-02
2026-4-10
```

이런 값이 섞이면 문자열 정렬은 실제 날짜 순서와 다르게 동작할 수 있습니다.

`compute_is_long_stay()`는 날짜 파싱 실패를 방어하지만, `detect_and_link_consecutive_stays()`는 문자열 비교를 그대로 사용합니다.

수정 제안:

- 자동 감지 함수에서도 날짜를 `date` 객체로 파싱해서 비교
- 파싱 실패한 예약은 스킵
- 스킵된 예약은 로그로 남김

우선순위: 중간

## 5. 자동 감지가 모든 확정 예약을 매번 훑음

위치: `backend/app/services/consecutive_stay.py`

`detect_and_link_consecutive_stays()`는 현재 테넌트의 모든 확정 예약을 가져옵니다.

예약 데이터가 적을 때는 괜찮지만, 데이터가 많이 쌓이면 아래 상황에서 부담이 될 수 있습니다.

- 네이버 동기화 후 자동 감지
- 수동 감지 API 호출
- 하루 4회 실행되는 스케줄러

수정 제안:

- 오늘 기준 최근 N개월 또는 특정 기간만 감지
- 단, 과거 예약 정합성까지 계속 보정해야 한다면 현재 방식 유지 가능

우선순위: 낮음에서 중간

## 6. 자동 감지와 수동 그룹의 정책 차이를 명확히 해야 함

자동 감지 함수는 `manual-`로 시작하는 그룹을 자동 해제하지 않습니다.

이건 사용자 의도를 존중하는 좋은 방어 코드입니다.

다만 운영 정책상 아래 질문을 정해야 합니다.

- 수동 그룹이 더 이상 날짜가 이어지지 않아도 계속 유지할 것인가?
- 수동 그룹 안 예약이 취소되면 어디까지 자동 정리할 것인가?
- 수동 그룹에 자동 감지가 새 예약을 붙여도 되는가?

현재 코드는 수동 그룹을 최대한 보존하는 방향입니다.

운영자가 직접 묶은 그룹을 시스템이 함부로 풀지 않는다는 장점이 있습니다.

반대로 잘못 묶인 수동 그룹은 자동으로 복구되지 않는다는 단점이 있습니다.

우선순위: 정책 결정 필요

## 추천 수정 순서

1. `link_reservations()`에 날짜 연속성 검증 추가
2. 서로 다른 기존 `stay_group_id`가 섞이면 에러 처리
3. `phone` 또는 `visitor_phone` 중 하나라도 있으면 자동 감지 대상에 포함
4. 자동 감지 날짜 비교를 문자열 비교에서 날짜 파싱 비교로 변경
5. 테스트 추가

## 추가하면 좋은 테스트

- 정상 자동 감지: 같은 이름/전화번호 + 이어진 날짜 예약 2건이 묶이는지
- 불연속 날짜: 같은 사람이어도 날짜가 이어지지 않으면 묶이지 않는지
- 수동 묶기 정상 케이스: 이어진 예약 2건이 `manual-` 그룹으로 묶이는지
- 수동 묶기 실패 케이스: 날짜가 이어지지 않으면 실패하는지
- 서로 다른 기존 그룹 섞기: 에러가 나는지
- visitor_phone-only 케이스: `phone`이 비어도 `visitor_phone`으로 감지되는지
- 그룹 해제: 2건 그룹에서 1건 해제 시 남은 1건의 그룹도 해체되는지
- 3건 그룹 해제: 가운데 예약 해제 후 남은 예약의 순서가 재정렬되는지

## 결론

가장 위험한 부분은 `link_reservations()`입니다.

이 함수는 프론트에서만 날짜 검증을 하고, 백엔드에서는 실제 연박인지 확인하지 않습니다.

연박 그룹은 SMS와 객실 배정에 영향을 주기 때문에, 잘못된 그룹이 만들어지면 단순 표시 오류가 아니라 운영 오류로 이어질 수 있습니다.

따라서 먼저 `link_reservations()`에 백엔드 검증을 추가하는 것이 좋습니다.

---

# custom_schedule_registry.py 수정 제안

이 문서는 `backend/app/services/custom_schedule_registry.py`를 기준으로, 현재 코드에서 수정하면 좋은 부분과 충돌이 우려되는 부분을 정리한 내용입니다.

## 핵심 요약

이 파일은 커스텀 SMS 스케줄의 "메뉴판"과 "발송 직전 보정 함수 연결표" 역할을 합니다.

예를 들어 아래 같은 커스텀 스케줄 타입을 프론트 드롭다운에 보여줍니다.

```text
인원 초과 (일반 객실)
인원 초과 (더블 객실, 업그레이드비 포함)
파티 당일 안내 (MMS, 2차 참여자)
```

그리고 실제 발송 직전에는 custom_type에 맞는 refresh handler를 찾아 실행합니다.

```text
surcharge_standard → _refresh_surcharge()
surcharge_double → _refresh_surcharge()
party3_today_mms → _refresh_party3_today_mms()
```

이 refresh handler는 SMS 발송 후보 칩 상태를 최신으로 맞추는 역할입니다.

## 1. CUSTOM_SCHEDULE_TYPES와 PRE_SEND_REFRESH_HANDLERS가 따로 관리됨

위치: `backend/app/services/custom_schedule_registry.py`

현재는 프론트에 보여줄 목록과 실제 실행할 handler 목록이 별도 딕셔너리로 나뉘어 있습니다.

```text
CUSTOM_SCHEDULE_TYPES
PRE_SEND_REFRESH_HANDLERS
```

문제 예시:

```text
CUSTOM_SCHEDULE_TYPES에는 새 타입을 추가함
PRE_SEND_REFRESH_HANDLERS에는 추가를 깜빡함
```

---

# room_auto_assign.py 수정 제안

이 문서는 `backend/app/services/room_auto_assign.py`를 기준으로, 현재 코드에서 버그 우려 지점, 충돌 가능성, 논리적 모순, 드문 케이스 리스크, 중복 및 삭제 후보를 정리한 내용입니다.

## 핵심 요약

이 파일은 특정 날짜의 **미배정 예약만** 골라 자동으로 객실을 채우는 서비스입니다.

기본 아이디어는 맞습니다.

- 예약의 `naver_biz_item_id`로 후보 객실 찾기
- 연박이면 전날 객실 우선 선호
- 도미토리면 수용 인원 체크
- 도미토리면 성별 혼숙 방지
- 기존 배정은 건드리지 않고 빈 배정만 채우기

하지만 현재 구현에는 아래 문제가 섞여 있습니다.

- 도메인 의미와 저장 구조가 충돌하는 부분
- 날짜 범위를 끝까지 보지 않는 검증
- 후보 객실 순서에 따라 결과가 달라지는 비직관적 분기
- 동시 실행 시 깨질 수 있는 부분
- 숫자 집계가 실제 의미와 어긋날 수 있는 부분

특히 가장 먼저 손봐야 할 곳은 **일반실 `booking_count` 처리**와 **도미토리 성별 검사의 날짜 범위**입니다.

## 전제: booking_count 해석은 맞지만 구현이 위험함

먼저 도메인 해석은 분명히 맞습니다.

```text
booking_count = 2
→ 한 사람이 방을 2개 예약한 예약 1건
→ "같은 예약이 같은 날짜에 방 2개를 점유"해야 함
```

즉 이 값은 "사람 2명"이 아니라 "객실 수량 2개"일 수 있습니다.

문제는 현재 `RoomAssignment` 저장 구조가 이 의미를 그대로 표현하지 못한다는 점입니다.

관련 위치:

- `backend/app/services/room_auto_assign.py`
- `backend/app/services/room_assignment.py`
- `backend/app/db/models.py`

현재 `RoomAssignment`는 아래 제약이 있습니다.

```text
UniqueConstraint("reservation_id", "date")
```

즉 같은 예약은 같은 날짜에 **방 1개만** 가질 수 있습니다.

그런데 자동배정 코드는 일반실에서 아래처럼 동작하려고 합니다.

```text
booking_count = 2
→ 방 2개 필요하다고 판단
→ 후보 방을 2개까지 assign_room() 호출
```

이 의도 자체는 도메인상 자연스럽습니다.

하지만 실제 저장 구조는 그걸 허용하지 않기 때문에, 현재 로직은 "지원하는 것처럼 보이지만 실제로는 깨질 수 있는 상태"입니다.

우선순위: 매우 높음

## 1. 일반실 booking_count 처리와 DB 구조가 충돌함

위치:

- `backend/app/services/room_auto_assign.py:379`
- `backend/app/db/models.py:308`
- `backend/app/services/room_assignment.py:514`

현재 일반실 분기는 아래 의미로 동작합니다.

```text
rooms_needed = booking_count
후보 일반실을 순서대로 돌면서
가능한 방을 여러 개 assign_room()
```

문제는 `assign_room()`이 새 방을 넣기 전에 **같은 reservation_id + 날짜 범위의 기존 RoomAssignment를 삭제**한다는 점입니다.

즉 이런 일이 가능합니다.

```text
1차 호출: R101 배정
2차 호출: 같은 reservation/date 범위의 기존 배정 삭제
2차 호출: R102 배정
결과: 마지막 방만 남음
```

이건 비즈니스 의도와 다릅니다.

의도:

```text
예약 1건이 방 2개를 점유
```

실제 저장 결과:

```text
예약 1건이 마지막 방 1개만 점유
```

이 문제 때문에 같이 따라오는 부작용도 있습니다.

- `assigned_details`에는 성공 2건처럼 쌓일 수 있음
- 실제 DB에는 마지막 객실만 남을 수 있음
- `assigned_count`와 실제 배정 상태가 다를 수 있음
- `unassigned` 계산이 음수가 되거나 왜곡될 수 있음

수정 제안:

- 선택지 A: 현재 모델을 유지할 거면 일반실에서 `booking_count > 1` 자동배정을 금지
- 선택지 B: 진짜 멀티룸을 지원할 거면 `RoomAssignment` 모델과 관련 로직을 다중 객실 점유가 가능하도록 재설계

개인적으로는 지금 상태에서 가장 안전한 방향은 아래입니다.

```text
단기:
  자동배정에서는 일반실 booking_count > 1 지원 중단 또는 명시적 실패 처리

중장기:
  멀티룸을 표현 가능한 스키마/모델로 재설계
```

우선순위: 매우 높음

## 2. assigned / unassigned 집계값이 실제 의미와 어긋날 수 있음

위치:

- `backend/app/services/room_auto_assign.py:71`
- `backend/app/services/room_auto_assign.py:148`

현재 집계는 대략 이런 식입니다.

```text
assigned_count = len(assigned_details)
unassigned = len(unassigned_candidates) - assigned_count
```

이 방식은 "배정 단위"가 항상 예약 1건당 1번일 때만 안전합니다.

그런데 현재 일반실 로직은 예약 1건에 대해 `assigned_details`를 여러 번 추가하려고 합니다.

그러면 다음 문제가 생깁니다.

- `assigned`가 예약 수인지 방 수인지 모호해짐
- `unassigned`가 실제 미배정 예약 수와 맞지 않음
- 활동 로그의 성공 수치도 왜곡될 수 있음

이건 운영자가 보고 판단하는 숫자를 틀리게 만들기 때문에 단순 표시 문제가 아닙니다.

수정 제안:

- `assigned`의 의미를 명확히 정해야 함
  - 예약 수 기준인지
  - 객실 수 기준인지
- 지금 API/로그/프론트 문구를 보면 예약 수처럼 읽히므로, 예약 기준 집계가 더 자연스럽습니다

우선순위: 높음

## 3. 도미토리 성별 충돌 검사가 target_date 하루만 봄

위치:

- `backend/app/services/room_auto_assign.py:342`
- `backend/app/services/room_auto_assign.py:367`

현재 도미토리 성별 락 검사는 **배정 시작일 하루만** 확인합니다.

하지만 실제 배정은 아래처럼 체크아웃 전까지 전체 날짜에 대해 생성됩니다.

```text
assign_room(db, res.id, room.id, target_date, res.check_out_date, ...)
```

즉 아래 같은 케이스가 생길 수 있습니다.

```text
예약 A: 남성 / 4월 24일~26일
객실 D1:
  4월 24일은 비어 있음
  4월 25일에는 여성 예약이 이미 있음
```

현재 로직은 4월 24일만 보고 통과시킬 수 있습니다.

그러면 결과는:

```text
4월 24일 배정 성공
4월 25일도 같은 방으로 배정 생성
→ 다음날 성별 혼합 발생 가능
```

상식적으로는 **숙박 기간 전체에 대해 성별 락을 검사**해야 맞습니다.

수정 제안:

- 도미토리 후보 검증 시 `target_date ~ check_out_date` 전체 날짜를 확인
- 각 날짜마다 기존 점유자의 성별을 확인해 하나라도 충돌하면 실패 처리

우선순위: 매우 높음

## 4. 후보 객실 순서에 따라 도미토리를 아예 시도하지 않을 수 있음

위치:

- `backend/app/services/room_auto_assign.py:332`
- `backend/app/services/room_auto_assign.py:378`

현재 후보 객실 목록은 `biz_item_id -> rooms`로 한 리스트에 들어옵니다.

즉 같은 상품에 아래처럼 섞여 있을 수 있습니다.

```text
후보 = [일반실 R101, 도미토리 D1, 도미토리 D2]
```

문제는 바깥 루프가 첫 번째 후보를 보고 분기를 정해버린다는 점입니다.

```text
첫 후보가 일반실이면
→ 일반실 분기 진입
→ break
→ 뒤에 있는 도미토리 후보는 검사조차 안 함
```

이건 굉장히 비직관적입니다.

같은 예약이라도 후보 순서가 아래처럼 달라지면 결과가 바뀔 수 있습니다.

```text
[일반실, 도미토리] → 실패
[도미토리, 일반실] → 성공
```

수정 제안:

- 일반실 후보와 도미토리 후보를 먼저 분리
- 예약 종류/상품 정책에 따라 어느 타입을 우선할지 명시적으로 결정
- "후보 순서에 따라 우연히 결과가 달라지는 구조"는 제거

우선순위: 높음

## 5. 도미토리 자동배정은 동시 실행에 취약함

위치:

- `backend/app/services/room_auto_assign.py`
- `backend/app/services/room_assignment.py`

현재 일반실은 `assign_room()` 내부에서 `SELECT ... FOR UPDATE`로 충돌을 어느 정도 방어합니다.

하지만 도미토리는 현재 흐름이 아래와 같습니다.

```text
1. check_capacity_all_dates()로 읽기
2. 현재 점유자 성별 확인
3. assign_room() 호출
```

이 사이에 다른 요청이나 스케줄러가 같은 도미토리 방에 배정하면:

- 둘 다 "자리 있음"으로 보고 통과
- 둘 다 insert 진행
- 결과적으로 침대 수 초과 가능
- bed_order 계산 꼬임 가능
- 성별 혼합 가능

특히 이 파일은 아래 경로로 동시에 들어올 수 있습니다.

- 수동 버튼 `POST /api/rooms/auto-assign`
- 매일 10:01 스케줄러
- 네이버 sync 후 후속 auto-assign

수정 제안:

- 도미토리도 assign 직전 재검증 또는 잠금 필요
- 가능하면 `(room_id, date)` 단위의 점유 계산에 대해 더 강한 동시성 제어 필요

우선순위: 높음

## 6. stay_group 선호 방 결정이 쿼리 순서에 의존함

위치:

- `backend/app/services/room_auto_assign.py:265`
- `backend/app/services/room_auto_assign.py:278`

현재 `stay_group_room_map` 은 `target_date` 와 `prev_date` 둘 다 조회한 뒤, 마지막으로 읽힌 `room_id` 하나만 남깁니다.

문제는:

- 정렬 기준이 없음
- "전날 방을 우선한다"는 정책이 코드상 보장되지 않음

즉 DB가 어떤 순서로 결과를 주느냐에 따라 다음 선호 방이 달라질 수 있습니다.

이건 재현이 어려운 유형이라 더 위험합니다.

수정 제안:

- 명시적으로 `prev_date` 우선
- 혹은 날짜별로 분리 조회
- "왜 이 방이 선호 방으로 선택됐는지" 코드에서 읽히게 만들기

우선순위: 중간

## 7. priority=0 주석 의미와 실제 정렬 동작이 어긋남

위치:

- `backend/app/db/models.py:220`
- `backend/app/services/room_auto_assign.py:207`

모델 주석은 아래 뜻으로 읽힙니다.

```text
0 = 미설정
낮을수록 먼저
```

그런데 정렬은 단순 오름차순입니다.

즉 실제 동작은:

```text
0인 방이 제일 먼저 온다
```

보통 "미설정"이면 아래처럼 기대합니다.

```text
명시 우선순위가 있는 방 먼저
미설정은 뒤
```

현재는 반대로 작동할 수 있어서, 운영자가 우선순위를 열심히 넣어도 `0`이 섞이면 결과가 직관과 다를 수 있습니다.

수정 제안:

- 정책을 하나로 확정해야 함
  - 정말 `0`이 최우선이면 주석 수정
  - `0=미설정`이면 정렬 시 뒤로 보내기

우선순위: 중간

## 8. 실패 사유는 마지막 후보의 상태만 남아 운영 판단을 왜곡할 수 있음

위치:

- `backend/app/services/room_auto_assign.py:330`
- `backend/app/services/room_auto_assign.py:414`

현재 `last_failure_reason` 하나만 기록합니다.

예를 들어 후보 방이 3개일 때:

```text
방 A: gender_lock
방 B: capacity_full
방 C: capacity_full
```

최종 기록은 `capacity_full` 하나만 남습니다.

하지만 운영자는 실제로는 아래처럼 이해해야 할 수 있습니다.

```text
일부 방은 성별 충돌
일부 방은 정원 초과
```

현재 로그는 원인을 단순화해서 보여주기 때문에, 설정 문제인지 수용량 문제인지 판단이 흐려질 수 있습니다.

수정 제안:

- 최소한 내부 로그에는 후보별 실패 이유를 남기기
- 사용자 표시용은 단일 reason 유지 가능
- 활동 로그 detail에는 `reasons_seen` 같은 보조 정보 추가 가능

우선순위: 중간

## 9. section 필터는 legacy/NULL 데이터에서 애매할 수 있음

위치:

- `backend/app/services/room_auto_assign.py:181`

현재 자동배정 대상 필터는 아래 의미입니다.

```text
section NOT IN ('party', 'unstable')
```

이 방식은 대부분 괜찮지만, `section` 이 `NULL` 인 legacy 데이터가 섞이면 SQL에서 예상과 다르게 빠질 수 있습니다.

즉 운영자는 "미배정인데 왜 후보에 안 잡히지?"라고 느낄 수 있습니다.

수정 제안:

- `section is null` 도 허용할지 정책 명시
- legacy 데이터 정리 전이라면 `or section is null` 고려

우선순위: 중간

## 10. check_out_date가 비어 있는 예약은 과도하게 살아남을 수 있음

위치:

- `backend/app/services/room_auto_assign.py:195`

현재 후처리 필터는 아래 의미입니다.

```text
check_out_date가 없으면 계속 active처럼 간주
```

정상 데이터라면 큰 문제는 없지만, 외부 sync 데이터가 깨졌을 때 아래 상황이 가능합니다.

```text
체크아웃 날짜 누락
→ 미래 날짜에도 계속 숙박 중으로 간주
→ 자동배정 대상에 남음
```

이건 흔한 케이스는 아니지만, 한 번 발생하면 운영자가 원인을 찾기 어렵습니다.

수정 제안:

- `check_out_date is None` 예약에 대한 별도 진단 로그
- 외부 sync 단계에서 데이터 품질 검증 강화

우선순위: 낮음에서 중간

## 11. 중복 후처리 가능성

위치:

- `backend/app/services/room_auto_assign.py:72`
- `backend/app/services/room_auto_assign.py:77`
- `backend/app/services/room_auto_assign.py:83`

현재 `assigned_reservation_ids` 는 중복 제거 없이 만듭니다.

일반실 multi-room 로직이 살아 있는 현재 구조에서는 같은 예약 ID가 여러 번 들어갈 수 있습니다.

그러면:

- `sync_sms_tags()` 중복 실행
- surcharge batch도 같은 예약을 중복 처리

가 발생할 수 있습니다.

지금 당장 큰 장애로 이어질 가능성은 낮지만, 불필요한 DB 부하와 로그 노이즈를 만듭니다.

수정 제안:

- 후처리 전 `reservation_id` dedupe

우선순위: 중간

## 12. flush가 과도하게 반복됨

위치:

- `backend/app/services/room_auto_assign.py:75`
- `backend/app/services/room_auto_assign.py:371`
- `backend/app/services/room_auto_assign.py:398`
- `backend/app/services/room_assignment.py:570`

`assign_room()` 내부에서 이미 flush를 여러 번 수행하는데, auto-assign 쪽에서 직후 또 flush 합니다.

기능상 꼭 필요한 부분이 아닌 곳이 섞여 있을 가능성이 높습니다.

이건 기능 버그보다는 성능/가독성 문제에 가깝습니다.

수정 제안:

- 어떤 flush가 진짜 필요한지 구분
- 중복 flush 정리

우선순위: 낮음에서 중간

## 삭제 후보 / 재설계 후보

### 1. 가장 강한 재설계 후보

위치:

- `backend/app/services/room_auto_assign.py:379`

현재 일반실 `booking_count` 기반 다중 배정 블록은 도메인 의도는 맞지만, 현재 모델 구조와 충돌합니다.

즉 이 코드는 단순 삭제보다는 아래 둘 중 하나가 필요합니다.

- 현재 모델에 맞게 단순화
- 멀티룸을 정식 지원하도록 전면 재설계

### 2. 삭제 가능성이 높은 보조 코드

위치:

- `backend/app/services/room_auto_assign.py:382`

`assigned_room_ids` 는 지금 구조에서는 실질 효과가 제한적입니다.

근본 문제는 "한 예약의 같은 날짜 다중 객실" 자체이기 때문에, 이 set은 표면만 가리는 코드에 가깝습니다.

### 3. 정리 가능한 중복 코드

위치:

- `backend/app/services/room_auto_assign.py:371`
- `backend/app/services/room_auto_assign.py:398`

직전 `assign_room()` 이 이미 flush 하는 흐름이라면 추가 flush는 삭제 후보입니다.

## 누락된 테스트

현재 테스트는 기본적인 실패 사유와 연박 선호는 보지만, 아래 핵심 리스크를 직접 검증하지 않습니다.

추가 권장 테스트:

- 일반실 `booking_count=2` 예약이 현재 구조에서 어떻게 저장되는지
- `assigned_count`, `unassigned` 가 왜곡되지 않는지
- 도미토리 연박 중 둘째 날에 성별 충돌이 있는 경우 실패하는지
- 후보 방에 일반실/도미토리가 같이 있을 때 순서에 따라 결과가 달라지지 않는지
- priority가 `0`일 때 기대 순서가 맞는지
- 동시 실행 시 도미토리 초과 배정이 없는지

## 추천 수정 순서

1. 일반실 `booking_count` 처리와 모델 구조 충돌부터 정리
2. 도미토리 성별 검사를 전체 숙박 기간 기준으로 수정
3. 후보 방 타입 혼합 시 분기 구조 정리
4. 도미토리 동시성 방어 보강
5. 집계값(`assigned`, `unassigned`) 의미 재정의
6. priority `0` 정책 정리
7. 중복 후처리/flush 정리

## 결론

이 파일은 방향 자체는 맞습니다.

특히 아래 철학은 좋습니다.

- 기존 배정을 덮어쓰지 않는 fill-only
- 연박자는 가능하면 같은 방 유지
- 도미토리 제약을 별도로 고려
- 실패를 조용히 삼키지 않고 활동 로그와 SSE로 알림

하지만 현재 구현은 몇 군데에서 **도메인 의도와 저장 구조가 어긋나고**, 그 결과 겉으로는 동작해도 실제 데이터나 집계가 틀어질 수 있습니다.

가장 위험한 부분은 일반실 `booking_count` 처리입니다.

이건 단순 if문 수정으로 끝나는 문제가 아니라,

```text
현재 시스템이 "예약 1건의 다중 객실 점유"를 진짜 지원하는지
아니면 자동배정에서는 단일 객실만 허용할지
```

를 먼저 결정해야 해결됩니다.

그 다음으로는 도미토리 성별 검사를 하루 단위가 아니라 **전체 숙박 날짜 범위**로 올리는 것이 필요합니다.
```

그러면 프론트 드롭다운에는 보이지만, 발송 직전 refresh는 실행되지 않습니다.

반대도 가능합니다.

```text
PRE_SEND_REFRESH_HANDLERS에는 handler가 있음
CUSTOM_SCHEDULE_TYPES에는 없음
```

그러면 코드상으로는 처리 가능한 타입인데 프론트에서는 선택할 수 없습니다.

수정 제안:

- 하나의 레지스트리 구조에서 `key`, `label`, `handler`를 같이 관리
- `get_custom_types()`는 그 레지스트리에서 label만 꺼내서 반환
- `get_pre_send_refresh_handler()`도 같은 레지스트리에서 handler를 꺼내서 반환

예상 구조:

```text
custom_type
label
pre_send_refresh_handler
```

우선순위: 높음

## 2. custom_type 검증이 부족함

위치: `backend/app/api/template_schedules.py`, `backend/app/services/custom_schedule_registry.py`

현재 스케줄 생성/수정 API는 `custom_type`이 실제 등록된 값인지 검증하지 않습니다.

문제 예시:

```text
custom_type = "surchage_standard"
```

`surcharge_standard`의 오타입니다.

이 값이 DB에 저장되면, 발송 시 `get_pre_send_refresh_handler()`는 handler를 찾지 못하고 `None`을 반환합니다.

그 결과 refresh 없이 발송 대상 계산이 진행될 수 있습니다.

수정 제안:

- 스케줄 생성 API에서 `schedule_category == "custom_schedule"`이면 `custom_type` 필수 검증
- `custom_type`이 등록된 타입인지 검증
- 스케줄 수정 API에서도 동일하게 검증
- 알 수 없는 `custom_type`이면 400 에러 반환

예상 에러:

```text
등록되지 않은 커스텀 스케줄 타입입니다.
```

우선순위: 높음

## 3. 등록되지 않은 custom_type이 조용히 통과함

위치: `backend/app/services/custom_schedule_registry.py`

현재 `get_pre_send_refresh_handler()`는 모르는 타입이면 그냥 `None`을 반환합니다.

```python
return PRE_SEND_REFRESH_HANDLERS.get(custom_type)
```

이 자체는 안전한 기본값처럼 보이지만, 운영에서는 오히려 문제를 숨길 수 있습니다.

문제 상황:

```text
DB에 잘못된 custom_type 저장
→ handler 없음
→ refresh 안 함
→ 로그도 거의 없음
→ 오래된 칩 기준으로 발송 가능
```

수정 제안:

- 등록된 타입인데 handler가 없는 경우 warning 로그
- 등록되지 않은 타입이면 warning 또는 에러 로그
- 중요한 커스텀 스케줄은 handler가 없으면 발송 중단도 고려

우선순위: 높음

## 4. refresh 실패를 삼키는 정책의 리스크

위치: `backend/app/scheduler/template_scheduler.py`

`custom_schedule_registry.py`에서 반환한 handler는 스케줄러에서 실행됩니다.

현재 스케줄러는 refresh handler가 실패해도 발송을 막지 않습니다.

```text
refresh 실패
→ 로그만 남김
→ 기존 칩 기준으로 발송 계속
```

장점:

- 일시적인 refresh 오류 때문에 전체 SMS 발송이 멈추지 않습니다.

단점:

- 오래된 칩 기준으로 잘못 발송될 수 있습니다.
- 특히 `surcharge_*`는 추가요금 안내라 오발송 리스크가 큽니다.

수정 제안:

- custom_type별 실패 정책을 분리
- 예: `surcharge_standard`, `surcharge_double`은 refresh 실패 시 발송 중단
- 예: 안내성 MMS는 기존처럼 refresh 실패를 로그만 남기고 진행

우선순위: 중간에서 높음

## 5. surcharge_standard와 surcharge_double이 같은 refresh를 중복 실행할 수 있음

위치: `backend/app/services/custom_schedule_registry.py`

현재 두 타입은 같은 handler를 사용합니다.

```text
surcharge_standard → _refresh_surcharge()
surcharge_double → _refresh_surcharge()
```

이 구조는 틀린 것은 아닙니다.

`reconcile_surcharge_batch()`가 내부에서 두 타입을 같이 정리한다면 오히려 자연스럽습니다.

다만 두 스케줄이 같은 시간에 실행되면 같은 날짜와 같은 예약들에 대해 refresh가 두 번 돌 수 있습니다.

문제:

- 예약 수가 많아지면 발송 직전 처리 시간이 늘어날 수 있음
- 같은 tick 안에서 같은 작업을 반복할 수 있음

수정 제안:

- 같은 실행 tick 안에서 `target_date`별 surcharge refresh를 한 번만 실행하도록 캐싱
- 또는 현재 구조를 유지하되 `reconcile_surcharge_batch()`는 반드시 idempotent해야 한다고 명시

우선순위: 중간

## 6. _refresh_surcharge()가 target_date의 모든 방 배정 예약을 재계산함

위치: `backend/app/services/custom_schedule_registry.py`

현재 `_refresh_surcharge()`는 해당 날짜의 모든 `RoomAssignment`를 조회합니다.

```text
target_date에 방 배정된 모든 예약
→ reconcile_surcharge_batch()
```

운영 규모가 작으면 괜찮습니다.

하지만 예약 수가 많아지면 발송 직전에 전체 재계산이 부담이 될 수 있습니다.

수정 제안:

- 처음에는 유지 가능
- 성능 문제가 생기면 변경된 예약만 추적하는 방식 고려
- 또는 custom_type별로 필요한 대상 범위를 더 좁히기

우선순위: 낮음에서 중간

## 7. get_custom_types()가 모든 타입을 모든 테넌트에 노출함

위치: `backend/app/services/custom_schedule_registry.py`

현재 등록된 커스텀 타입은 모든 테넌트/환경에서 동일하게 노출됩니다.

문제는 일부 타입이 특정 테넌트 정책에 의존할 수 있다는 점입니다.

예를 들어 `surcharge_double`은 더블룸 상품 ID 정책과 연결되어 있습니다.

그런데 다른 테넌트에는 해당 상품이 없거나 기준이 다를 수 있습니다.

수정 제안:

- 테넌트별 노출 가능 custom_type 설정
- 최소한 타입별 의존 정책을 주석이나 설정으로 명확히 분리

우선순위: 중간

## 8. 프론트 custom type 목록 로딩 실패를 무시함

위치: `frontend/src/pages/Templates.tsx`

현재 프론트는 커스텀 타입 목록 조회 실패를 조용히 무시합니다.

```text
GET /api/template-schedules/custom-types 실패
→ 아무 안내 없음
→ 드롭다운 비어 있음
```

사용자는 왜 커스텀 로직을 선택할 수 없는지 알기 어렵습니다.

수정 제안:

- 실패 시 toast 표시
- custom type 목록이 비어 있으면 커스텀 스케줄 선택 비활성화
- 또는 "커스텀 로직 목록을 불러오지 못했습니다" 안내 표시

우선순위: 낮음에서 중간

## 추천 수정 순서

1. 스케줄 생성/수정 API에서 `custom_type` 검증 추가
2. `CUSTOM_SCHEDULE_TYPES`와 `PRE_SEND_REFRESH_HANDLERS`를 하나의 레지스트리 구조로 통합
3. 알 수 없는 `custom_type` 실행 시 warning 로그 추가
4. `surcharge_*` refresh 실패 시 발송을 계속할지 중단할지 정책 결정
5. 프론트 custom type 로딩 실패 UX 개선
6. 필요하면 surcharge refresh 중복 실행 최적화

## 추가하면 좋은 테스트

- `GET /api/template-schedules/custom-types`가 등록된 타입 목록을 반환하는지
- 등록되지 않은 `custom_type`으로 스케줄 생성 시 400이 나는지
- `custom_schedule`인데 `custom_type`이 없으면 400이 나는지
- `surcharge_standard`가 `_refresh_surcharge()` handler를 찾는지
- `party3_today_mms`가 `_refresh_party3_today_mms()` handler를 찾는지
- handler가 없는 타입이 들어왔을 때 warning 로그가 남는지
- refresh 실패 시 custom_type별 정책대로 발송을 중단하거나 계속하는지
- surcharge refresh를 반복 호출해도 칩 상태가 깨지지 않는지

## 결론

가장 위험한 부분은 custom_type 등록과 실행 handler가 분리되어 있다는 점입니다.

프론트에는 보이지만 실제 refresh가 안 되거나, DB에 오타 custom_type이 저장되어도 조용히 넘어갈 수 있습니다.

커스텀 스케줄은 일반 스케줄보다 조건이 복잡하고, 특히 추가요금 안내처럼 민감한 메시지를 다룰 수 있습니다.

따라서 먼저 `custom_type` 검증과 레지스트리 통합을 처리하는 것이 좋습니다.

---

# filters.py 수정 제안

이 문서는 `backend/app/services/filters.py`를 기준으로, 현재 코드에서 수정하면 좋은 부분, 충돌이 우려되는 부분, 삭제 가능 후보, 논리적으로 애매한 부분을 정리한 내용입니다.

## 핵심 요약

`filters.py`는 SMS 스케줄의 대상자를 고르는 필터 엔진입니다.

프론트에서 아래 같은 조건을 설정하면:

```text
객실 예약자
본관만
미배정도 포함
연박자는 제외
메모에 특정 문구 포함
```

이 파일이 그 조건을 실제 DB 조회 조건으로 바꿉니다.

```text
스케줄 필터 JSON
→ SQLAlchemy 조건
→ SMS 발송 대상 예약자 조회
```

이 파일은 SMS 오발송과 직접 연결됩니다. 필터가 잘못 해석되면 "안 보내야 할 사람에게 SMS가 가는 문제"가 생길 수 있습니다.

## 1. v1/v2가 섞인 필터에서 v2 옵션이 유실될 수 있음

위치: `backend/app/services/filters.py`

현재 `_is_v2_shape()`는 필터 전체를 보고 v1인지 v2인지 판단합니다.

문제는 v2 필터에 legacy 필터가 하나 섞인 경우입니다.

예시:

```json
[
  {
    "type": "assignment",
    "value": "room",
    "buildings": [1],
    "stay_filter": "exclude"
  },
  {
    "type": "room",
    "value": "ghost"
  }
]
```

이 경우 v2 옵션인 `buildings`, `stay_filter`가 이미 있는데도, legacy 타입 때문에 v1 변환 경로를 탈 수 있습니다.

그 결과 `stay_filter` 같은 중요한 옵션이 사라질 수 있습니다.

수정 제안:

- 필터 전체가 v1인지 v2인지 판단하기보다, item 단위로 정규화
- 이미 `assignment` 안에 `buildings`, `include_unassigned`, `stay_filter`가 있으면 반드시 보존
- legacy 타입만 개별적으로 변환 또는 제거

우선순위: 높음

## 2. extract_stay_filter()가 여러 room 필터 중 첫 번째만 봄

위치: `backend/app/services/filters.py`

현재 `extract_stay_filter()`는 첫 번째 `assignment: room` 필터만 봅니다.

문제 예시:

```json
[
  {
    "type": "assignment",
    "value": "room",
    "buildings": [1]
  },
  {
    "type": "assignment",
    "value": "room",
    "buildings": [2],
    "stay_filter": "exclude"
  }
]
```

두 번째 room 필터에 `stay_filter: exclude`가 있어도 첫 번째만 보고 `None`을 반환할 수 있습니다.

수정 제안:

- 모든 room 필터를 확인
- 하나라도 `stay_filter == "exclude"`이면 exclude로 판단
- 또는 저장 단계에서 room 필터를 하나로 병합

우선순위: 높음

## 3. assignment: room의 의미가 애매함

위치: `backend/app/services/filters.py`

현재 `assignment: room` 필터는 건물 조건이 없으면 `Reservation.section == "room"`만 확인합니다.

```text
건물 조건 없음
→ section이 room이면 통과
```

하지만 건물 조건이 있으면 `RoomAssignment`도 확인합니다.

```text
건물 조건 있음
→ 해당 날짜에 해당 건물 방에 배정되어 있어야 통과
```

즉, 같은 "객실 예약" 필터인데 조건 유무에 따라 판단 기준이 달라집니다.

논리적으로 애매한 부분:

```text
객실 예약자 = section이 room인 예약자인가?
객실 예약자 = 해당 날짜에 실제 방 배정이 있는 예약자인가?
```

운영 의도가 "객실 섹션 예약자"라면 현재 로직이 맞습니다.

운영 의도가 "실제로 객실 배정된 예약자"라면 건물 조건이 없어도 `RoomAssignment.date == target_date`를 확인해야 합니다.

수정 제안:

- `assignment: room`의 의미를 정책으로 확정
- 실제 배정 기준이면 `_condition_room()`에서 항상 `RoomAssignment` 존재 여부 확인
- 현재 의미를 유지한다면 UI 라벨을 "객실 예약"으로 명확히 유지

우선순위: 중간에서 높음

## 4. include_unassigned와 건물 필터 조합이 직관과 다를 수 있음

위치: `backend/app/services/filters.py`

현재 "본관 + 미배정 포함" 조건의 의미는 아래와 같습니다.

```text
본관에 배정된 객실 예약자
OR
모든 미배정 예약자
```

미배정 예약자는 건물이 없기 때문에 기술적으로는 자연스럽습니다.

하지만 사용자는 "본관 관련 대상 + 미배정" 정도로 이해할 수 있고, 실제로는 건물과 무관한 모든 미배정자가 포함됩니다.

수정 제안:

- UI에 "미배정은 건물 구분 없이 포함됩니다" 안내
- 또는 미배정 포함 옵션을 별도 assignment 필터로 분리
- 운영상 이 의미가 맞는지 정책 확인

우선순위: 중간

## 5. unknown filter를 조용히 무시함

위치: `backend/app/services/filters.py`

현재 알 수 없는 필터 타입은 실행 시 그냥 무시됩니다.

문제 예시:

```json
{
  "type": "assigment",
  "value": "room"
}
```

`assignment` 오타인데 서버는 이 필터를 무시합니다.

그 결과 필터가 없는 것처럼 동작해 발송 대상이 넓어질 수 있습니다.

수정 제안:

- 스케줄 생성/수정 API에서는 unknown filter를 400으로 막기
- 기존 DB 데이터 읽기나 마이그레이션 경로에서는 warning 로그만 남기기
- 실행 시 unknown filter가 있으면 warning 이상 로그 남기기

우선순위: 높음

## 6. _parse_filters()가 잘못된 JSON을 빈 필터로 처리함

위치: `backend/app/services/filters.py`

현재 잘못된 JSON이면 `[]`를 반환합니다.

문제:

```text
필터 JSON 깨짐
→ 빈 필터로 해석
→ 필터 없음
→ 대상자가 넓어질 수 있음
```

SMS 필터에서는 "필터가 실패해서 안 보내짐"보다 "필터가 풀려서 많이 보내짐"이 더 위험합니다.

수정 제안:

- 생성/수정 API에서는 유효한 list인지 강하게 검증
- 스케줄 실행 시 invalid JSON이면 발송 중단 또는 critical 로그
- API 응답용 파싱에서는 기존처럼 빈 배열 fallback 가능

우선순위: 높음

## 7. only_date_independent=True 이름과 실제 동작이 완전히 맞지 않음

위치: `backend/app/services/filters.py`

`only_date_independent=True`는 칩 후보를 넓게 잡기 위해 날짜 의존 필터 일부를 건너뛰는 옵션입니다.

그런데 `assignment: unstable`은 내부에서 `target_date`를 사용합니다.

즉, 이름만 보면 날짜 독립 필터만 적용하는 것 같지만, 일부 날짜 의존 로직이 남아 있을 수 있습니다.

수정 제안:

- `only_date_independent=True`일 때 unstable의 daily_info 조건도 제외할지 결정
- 함수 인자 이름을 실제 용도에 맞게 변경 검토
- 예: `for_candidate_prefilter=True`

우선순위: 중간

## 8. column_match value 문자열 포맷이 취약함

위치: `backend/app/services/filters.py`

`column_match`는 현재 문자열 하나에 정보를 넣습니다.

```text
column:operator:text
```

예시:

```text
notes:contains:VIP
party_type:is_not_empty:
```

현재 코드는 `split(':', 2)`를 사용해서 text 안에 콜론이 들어가는 경우는 어느 정도 처리됩니다.

하지만 구조적으로는 문자열 포맷이라 검증이 약합니다.

수정 제안:

- 장기적으로는 v2 구조처럼 객체 형태로 바꾸는 것이 안전

예상 구조:

```json
{
  "type": "column_match",
  "column": "notes",
  "operator": "contains",
  "text": "VIP"
}
```

우선순위: 낮음에서 중간

## 삭제 가능 후보

지금 당장 삭제해도 안전한 코드는 거의 없습니다.

다만 조건부 삭제 후보는 있습니다.

## 삭제 후보 1. v1 호환 코드

위치: `backend/app/services/filters.py`

대상:

```text
building
room
room_assigned
party_only
```

이 코드는 과거 필터 형식을 새 v2 형식으로 읽기 위한 호환 코드입니다.

삭제 조건:

- DB에 저장된 모든 `TemplateSchedule.filters`가 v2로 마이그레이션 완료
- 마이그레이션 검증 쿼리에서 v1 타입이 0건
- 프론트와 백엔드 어디에서도 v1 타입을 더 이상 생성하지 않음
- 관련 테스트를 v2 기준으로 갱신

현재는 바로 삭제 비추천입니다.

## 삭제 후보 2. legacy TemplateSchedule.stay_filter fallback

위치: `backend/app/services/filters.py`

v2에서는 `stay_filter`가 room assignment 안에 들어갑니다.

프론트도 현재 payload에서 legacy `stay_filter`를 `null`로 보냅니다.

하지만 기존 DB 데이터가 아직 legacy 컬럼을 쓸 수 있으므로 fallback이 남아 있습니다.

삭제 조건:

- 기존 `TemplateSchedule.stay_filter` 데이터가 모두 v2 filters로 이동
- 더 이상 legacy 컬럼을 읽지 않기로 결정
- 마이그레이션 완료 후 컬럼 제거 또는 fallback 제거

현재는 바로 삭제 비추천입니다.

## 삭제 후보 3. passthrough 보존 정책

위치: `backend/app/services/filters.py`

현재 `_normalize_to_v2()`는 알 수 없는 필터를 보존합니다.

이건 데이터 유실 방지에는 좋습니다.

하지만 발송 필터 관점에서는 오타를 숨길 수 있습니다.

추천 정책:

- normalize 단계에서는 보존
- API 생성/수정 단계에서는 unknown filter 금지
- 실행 단계에서는 unknown filter warning

즉, 삭제보다는 검증 정책을 추가하는 방향이 좋습니다.

## 논리적으로 이치에 맞지 않거나 애매한 부분

가장 애매한 부분은 `assignment: room`입니다.

현재 기준:

```text
건물 필터 없음
→ section == room

건물 필터 있음
→ section == room AND 해당 날짜 RoomAssignment가 해당 건물
```

같은 필터인데 상황에 따라 기준이 다릅니다.

이게 운영 의도와 맞는지 확인이 필요합니다.

두 번째로 애매한 부분은 `include_unassigned`입니다.

현재 기준:

```text
건물 필터 + 미배정 포함
→ 해당 건물 객실 예약자 + 모든 미배정자
```

이것도 의도한 정책이면 괜찮지만, UI에서 명확히 보여주는 것이 좋습니다.

## 추천 수정 순서

1. 스케줄 생성/수정 API에서 filter schema 검증 추가
2. `_normalize_to_v2()`를 item 단위 정규화로 변경해 v2 옵션 유실 방지
3. `extract_stay_filter()`가 모든 room 필터를 확인하도록 수정
4. `assignment: room`의 의미를 정책으로 확정
5. invalid JSON / unknown filter 실행 시 warning 또는 발송 중단 정책 결정
6. `include_unassigned`의 의미를 UI에 명확히 표시
7. DB 마이그레이션 완료 후 v1 호환 코드 제거 검토

## 추가하면 좋은 테스트

- v2 필터에 legacy ghost 필터가 섞여도 `buildings`, `stay_filter`가 보존되는지
- room 필터가 여러 개일 때 하나라도 `stay_filter: exclude`이면 연박자가 제외되는지
- unknown filter type이 생성/수정 API에서 400 처리되는지
- invalid JSON filters를 가진 스케줄 실행이 안전하게 막히거나 경고 로그를 남기는지
- 건물 필터 + `include_unassigned` 조합이 의도한 대상자를 반환하는지
- `assignment: room`이 실제 방 배정 기준인지 section 기준인지 정책에 맞게 동작하는지
- `only_date_independent=True`일 때 unstable 필터가 의도대로 후보를 넓게 잡는지

## 결론

`filters.py`에서 지금 당장 삭제할 코드는 거의 없습니다.

대부분은 v1/v2 전환기 호환 코드라서, DB 마이그레이션 확인 없이 삭제하면 기존 스케줄 필터가 깨질 수 있습니다.

가장 위험한 부분은 잘못된 필터가 조용히 무시되거나 빈 필터로 해석되어 SMS 발송 대상이 넓어지는 것입니다.

따라서 우선은 삭제보다 검증 강화가 먼저입니다.

---

# naver_sync.py 수정 제안

이 문서는 `backend/app/services/naver_sync.py`를 기준으로, 현재 코드에서 수정하면 좋은 부분, 충돌이 우려되는 부분, 삭제 가능 후보, 논리적으로 애매한 부분을 정리한 내용입니다.

## 핵심 요약

`naver_sync.py`는 네이버 예약 데이터를 가져와 우리 시스템의 예약 데이터로 맞추는 동기화 파이프라인입니다.

이 파일은 단순히 예약만 저장하지 않습니다.

아래 작업들이 한 번의 동기화 안에서 같이 일어납니다.

```text
네이버 예약 조회
→ 예약 생성/수정
→ 취소 처리
→ 연박 감지
→ 객실 자동 배정
→ SMS 칩 재계산
→ surcharge 칩 재계산
→ 활동 로그/diag 로그 기록
```

따라서 이 파일의 오류는 예약, 객실 배정, SMS 발송 대상까지 동시에 영향을 줄 수 있습니다.

## 1. 메인 함수 안에서 commit/rollback이 여러 번 나뉘어 있음

위치: `backend/app/services/naver_sync.py`

현재 `sync_naver_to_db()`는 중간중간 commit을 합니다.

```text
예약 저장 commit
연박 감지 commit
자동 배정 commit
칩 재계산 commit
```

장점:

- 한 단계가 실패해도 앞 단계 데이터는 남습니다.

단점:

- 전체 동기화가 하나의 원자적 작업으로 처리되지 않습니다.
- 중간 단계가 실패하면 데이터 상태가 어중간할 수 있습니다.

문제 예시:

```text
예약 저장 성공
연박 감지 성공
자동 배정 실패
칩 재계산 실패
그래도 최종 응답은 success=True
```

이 경우 예약은 생겼지만 방 배정이나 SMS 칩은 최신 상태가 아닐 수 있습니다.

수정 제안:

- 부분 성공을 허용한다면 결과에 실패한 phase를 명확히 포함
- 예: `phase_errors`, `partial_success`
- phase별 실패를 activity log에 남기기
- 원자성이 더 중요하다면 트랜잭션 경계 재설계

우선순위: 높음

## 2. updated_count가 실제 변경 여부와 관계없이 증가함

위치: `backend/app/services/naver_sync.py`

현재 기존 예약이면 실제 변경이 없어도 `updated_count`가 증가합니다.

```python
if existing:
    _update_reservation(...)
    updated_count += 1
```

문제:

- "갱신 N건"이 실제 변경 건수처럼 보입니다.
- 운영 로그와 대시보드 해석이 헷갈릴 수 있습니다.
- 후속 작업 조건에도 영향을 줄 수 있습니다.

수정 제안:

- `_update_reservation()`이 실제 변경 여부를 bool로 반환
- 실제 변경된 경우만 `updated_count` 증가
- 또는 이름을 `existing_count`로 바꿔 의미를 명확히 하기

우선순위: 중간에서 높음

## 3. 연박 감지가 업데이트 건수만 있어도 전체 예약을 스캔함

위치: `backend/app/services/naver_sync.py`

현재 연박 감지 조건은 아래와 같습니다.

```python
if added_count > 0 or updated_count > 0:
```

그런데 `updated_count`는 기존 예약이면 거의 항상 증가합니다.

결과적으로 네이버 동기화가 실행될 때마다 `detect_and_link_consecutive_stays()`가 현재 테넌트의 확정 예약 전체를 훑을 수 있습니다.

수정 제안:

- 실제로 이름, 전화번호, 날짜, 상태가 바뀐 경우에만 연박 감지 실행
- 또는 `added_count > 0 or date_changed_ids` 기준으로 축소
- 취소로 인한 unlink는 `_update_reservation()` 안에서 별도로 처리되므로 같이 고려

우선순위: 중간

## 4. chip_target_ids가 신규/날짜 변경 예약만 포함함

위치: `backend/app/services/naver_sync.py`

현재 SMS 칩 재계산 대상은 아래 두 종류입니다.

```text
신규 예약
날짜가 변경된 예약
```

하지만 SMS 필터에 영향을 주는 필드는 날짜 외에도 많습니다.

예:

```text
party_type
notes
gender
naver_room_type
section
party_size
male_count
female_count
is_long_stay
```

문제 예시:

```text
기존 예약의 gender가 변경됨
→ gender 필터 스케줄 대상이 달라져야 함
→ 날짜는 안 바뀜
→ chip_target_ids에 포함되지 않음
→ SMS 칩이 오래된 상태로 남을 수 있음
```

수정 제안:

- `_update_reservation()`이 "칩 재계산 필요 여부"를 반환
- 날짜 변경뿐 아니라 필터 영향 필드 변경도 `chip_target_ids`에 포함
- `reservations.py`의 `_SMS_TAG_FIELDS` 기준과 맞추기

우선순위: 높음

## 5. source="unstable"이어도 booking_source는 "naver"로 저장됨

위치: `backend/app/services/naver_sync.py`

현재 `_create_reservation()`은 source를 받지 않고 무조건 아래처럼 저장합니다.

```python
booking_source = "naver"
```

그런데 메인 함수에는 `source="unstable"` 흐름이 있습니다.

문제:

```text
source는 unstable
booking_source는 naver
section은 unstable
```

이 구조는 데이터 의미가 애매합니다.

`booking_source`가 "네이버에서 온 예약"이라는 뜻이라면 현재가 맞습니다.

하지만 stable/unstable 출처를 구분하려는 값이라면 현재 구조는 부족합니다.

수정 제안:

- `booking_source`의 의미를 정책으로 확정
- unstable을 구분해야 한다면 `booking_source="unstable"` 또는 별도 source 필드 추가
- 기존 화면/필터가 `booking_source == "naver"`를 기대하는지 확인 후 마이그레이션

우선순위: 중간

## 6. 알 수 없는 status를 CONFIRMED로 저장함

위치: `backend/app/services/naver_sync.py`

현재 `_create_reservation()`은 네이버 status 변환에 실패하면 `CONFIRMED`로 저장합니다.

```python
except ValueError:
    status_enum = ReservationStatus.CONFIRMED
```

문제:

```text
알 수 없는 상태값
→ 확정 예약으로 저장
→ 자동 객실 배정 대상
→ SMS 칩 생성 대상
```

모르는 값은 보수적으로 처리하는 것이 맞습니다.

수정 제안:

- 알 수 없는 status는 warning 로그
- 기본값을 `PENDING`으로 둘지, 해당 예약을 skip할지 정책 결정
- 최소한 `CONFIRMED` fallback은 위험하므로 수정 필요

우선순위: 높음

## 7. 당일 취소 처리에서 deprecated 필드를 직접 만짐

위치: `backend/app/services/naver_sync.py`

당일 취소 시 아래 필드를 직접 비웁니다.

```python
existing.room_number = None
existing.room_password = None
```

하지만 현재 객실 정보의 source of truth는 `RoomAssignment`입니다.

문제:

- deprecated 성격의 denormalized 필드를 계속 갱신하고 있음
- 향후 `RoomAssignment` 중심 정책과 충돌 가능

수정 제안:

- 이 필드가 아직 UI/API fallback에 필요한지 확인
- 필요 없다면 제거 후보
- 필요하다면 "cleanup 목적"이라는 주석을 명확히 남기기

우선순위: 낮음에서 중간

## 8. surcharge reconcile이 오늘 날짜만 대상으로 함

위치: `backend/app/services/naver_sync.py`

현재 동기화 후 surcharge 재계산은 오늘 날짜만 대상으로 합니다.

```python
today_str = datetime.now(KST).strftime("%Y-%m-%d")
reconcile_surcharge_batch(db, chip_target_ids, today_str)
```

문제:

- 내일 이후 예약이 새로 들어왔거나 날짜가 바뀐 경우, 해당 날짜의 surcharge 칩이 즉시 최신화되지 않을 수 있습니다.
- 발송 직전 refresh가 있다면 최종 발송은 보정될 수 있지만, UI 칩은 늦게 맞을 수 있습니다.

수정 제안:

- `chip_target_ids` 예약의 실제 체류 날짜 전체를 대상으로 surcharge reconcile
- 또는 "surcharge는 발송 직전 refresh가 최종 기준"이라는 정책을 명시

우선순위: 중간

## 9. _align_bed_orders_for_groups()가 전체 stay_group을 매번 훑음

위치: `backend/app/services/naver_sync.py`

연박 감지에서 새 링크가 생기면 전체 stay_group 예약을 조회합니다.

```text
stay_group_id가 있는 모든 예약 조회
```

문제:

- 새로 연결된 그룹만 정렬하면 되는데 전체 그룹을 훑습니다.
- 데이터가 많아지면 비용이 늘어납니다.

수정 제안:

- `detect_and_link_consecutive_stays()`가 변경된 group_id 목록을 반환
- 변경된 그룹만 bed_order 정렬
- 현재 규모가 작다면 유지 가능

우선순위: 낮음에서 중간

## 10. _parse_gender_from_custom_form() 파싱이 단순함

위치: `backend/app/services/naver_sync.py`

현재는 텍스트 안의 `남`, `여` 등장 횟수를 셉니다.

문제 가능성:

```text
남성 2명, 여성 1명
남/여 문의
남자친구
```

같은 표현에서 오탐할 수 있습니다.

다만 `total`과 합계가 맞을 때만 사용하는 방어가 있어 일부 위험은 줄어듭니다.

수정 제안:

- 실제 네이버 custom form 샘플을 기준으로 정규식 개선
- 파싱 성공/실패율 로그 추가

우선순위: 낮음

## 삭제 가능 후보

## 삭제 후보 1. 오래된 Phase 3 주석

위치: `backend/app/services/naver_sync.py`, `backend/app/scheduler/jobs.py`

상단 docstring과 scheduler 주석에는 아직 Phase 3 1차 칩 reconcile이 있는 것처럼 설명되어 있습니다.

하지만 현재 코드는 Phase 3을 제거하고 Phase 5 이후 통합 1회로 바꿨습니다.

삭제/수정 대상:

- "Phase 3: reconcile_chips_for_reservation (1차)" 표현 수정
- "방 미배정 상태, building 칩 미생성" 같은 오래된 설명 제거
- 실제 코드 흐름에 맞게 "Phase 5 이후 통합 reconcile"로 정리

우선순위: 중간

## 삭제 후보 2. target_date 인자

위치: `backend/app/services/naver_sync.py`

`sync_naver_to_db()`는 `target_date` 인자를 받지만, 함수 내부에서는 provider에 그대로 넘기는 역할만 합니다.

```python
reservation_provider.sync_reservations(target_date, from_date=from_date)
```

삭제 가능 여부:

- provider 인터페이스가 실제로 `target_date`를 쓰는지 확인 필요
- 외부 provider 호환 인자라면 유지
- 사용처가 없다면 제거 가능

현재만 보고 바로 삭제는 비추천입니다.

## 삭제 후보 3. existing.room_number / existing.room_password 직접 세팅

위치: `backend/app/services/naver_sync.py`

현재 구조상 객실 정보의 기준은 `RoomAssignment`입니다.

따라서 당일 취소 시 denormalized 필드를 직접 비우는 코드는 제거 후보입니다.

삭제 조건:

- API/UI에서 해당 필드 fallback을 완전히 제거했는지 확인
- `clear_all_for_reservation()`의 cleanup 정책과 맞추기
- 운영 데이터에서 해당 필드를 더 이상 사용하지 않는지 확인

현재는 바로 삭제보다 사용 여부 확인이 먼저입니다.

## 삭제 후보 4. _align_bed_orders_for_groups() 전체 스캔 방식

이 함수 자체는 필요합니다.

다만 전체 stay_group을 훑는 방식은 최적화 후보입니다.

삭제가 아니라 "변경된 그룹만 처리"로 줄이는 것이 좋습니다.

## 논리적으로 이치에 맞지 않거나 애매한 부분

## 1. source와 booking_source의 의미가 다름

현재 `source="unstable"`로 동기화해도 `booking_source`는 `"naver"`입니다.

이게 아래 중 어떤 의미인지 정해야 합니다.

```text
booking_source = 외부 플랫폼 출처
booking_source = stable/unstable 업무 출처
```

전자의 의미라면 현재가 맞고, 후자의 의미라면 수정이 필요합니다.

## 2. 알 수 없는 status를 확정 예약으로 처리함

이건 논리적으로 위험합니다.

```text
모르는 상태
→ 확정 예약
```

보수적인 시스템에서는 모르는 값은 `PENDING`, skip, 또는 에러 로그가 맞습니다.

## 3. updated_count의 의미가 이름과 다름

현재 `updated_count`는 실제로 "변경된 예약 수"라기보다 "기존 예약으로 처리한 수"에 가깝습니다.

이름이 운영 로그 해석을 헷갈리게 합니다.

## 4. 후처리 실패에도 success=True가 될 수 있음

연박 감지, 자동 배정, 칩 재계산이 실패해도 메인 함수는 마지막에 `success: True`를 반환할 수 있습니다.

부분 성공 정책이라면 괜찮지만, 응답에 그 사실이 드러나야 합니다.

## 추천 수정 순서

1. `_update_reservation()`이 실제 변경 여부와 칩 재계산 필요 여부를 반환하도록 수정
2. `chip_target_ids` 기준을 날짜 변경뿐 아니라 필터 영향 필드 변경까지 확대
3. 알 수 없는 status를 `CONFIRMED`로 저장하지 않도록 정책 수정
4. `sync_naver_to_db()` 결과에 phase별 실패 정보 포함
5. 오래된 Phase 3 주석 정리
6. `source="unstable"` 저장 정책 확정
7. surcharge reconcile 날짜 범위 확대 또는 발송 직전 refresh 정책 명시
8. `_align_bed_orders_for_groups()`를 변경된 그룹만 처리하도록 최적화

## 추가하면 좋은 테스트

- 기존 예약 데이터가 실제로 바뀌지 않으면 `updated_count`가 증가하지 않는지
- gender/naver_room_type/party_type 등 필터 영향 필드 변경 시 SMS 칩이 재계산되는지
- 알 수 없는 status가 들어왔을 때 확정 예약으로 저장되지 않는지
- 자동 배정 실패 시 결과에 partial failure 정보가 포함되는지
- chip reconcile 실패 시 activity log 또는 응답에 실패 phase가 남는지
- unstable 동기화 예약의 source 정책이 일관되게 저장되는지
- 내일 이후 예약의 surcharge 칩이 필요한 날짜에 재계산되는지
- 연박 감지 후 변경된 그룹만 bed_order 정렬되는지
- 당일 취소 시 RoomAssignment와 SMS/surcharge 칩이 올바르게 정리되는지

## 결론

`naver_sync.py`에서 가장 먼저 볼 부분은 `chip_target_ids`와 status fallback입니다.

현재 구조에서는 예약 정보가 바뀌어도 날짜가 안 바뀌면 SMS 칩이 오래된 상태로 남을 수 있습니다.

또 알 수 없는 네이버 status가 확정 예약으로 들어오면 자동 객실 배정과 SMS 발송 대상까지 이어질 수 있습니다.

이 두 가지가 운영 리스크가 가장 큽니다.

---

# party3_mms.py 수정 제안

이 문서는 `backend/app/services/party3_mms.py`에서 요청한 항목만 정리한 내용입니다.

포함 범위:

- 4번: 템플릿 비활성 상태 처리
- 7번: tenant context 처리
- 삭제 가능 후보

## 1. schedule.template 활성 여부를 확인하지 않음

위치: `backend/app/services/party3_mms.py`

현재 `reconcile_party3_mms()`는 스케줄과 템플릿 객체가 존재하는지만 확인합니다.

```python
if not schedule or not schedule.template:
    return
```

문제:

- 연결된 템플릿이 비활성화되어 있어도 MMS 칩이 생성될 수 있습니다.
- 실제 발송 단계에서는 템플릿 비활성 때문에 막힐 수 있지만, 칩이 먼저 생기면 UI나 운영자가 보기에는 혼란스럽습니다.

수정 제안:

- `schedule.template.is_active`도 확인
- 템플릿이 비활성화되어 있으면 새 칩을 만들지 않기
- 필요하면 해당 스케줄의 미발송 칩을 삭제할지도 정책 결정

예상 수정 방향:

```text
스케줄 없음 → 종료
템플릿 없음 → 종료
템플릿 비활성 → 종료 또는 미발송 칩 정리
```

우선순위: 중간

## 2. tenant_id가 None이어도 칩 생성 시도 가능

위치: `backend/app/services/party3_mms.py`

현재 칩 생성 시 tenant_id는 ContextVar에서 가져옵니다.

```python
tenant_id = current_tenant_id.get()
```

일반 API/스케줄러 흐름에서는 tenant context가 잡혀 있어서 보통 문제 없습니다.

하지만 테스트, 수동 호출, 잘못된 백그라운드 실행 흐름에서는 `tenant_id`가 `None`일 수 있습니다.

문제:

- `tenant_id=None`으로 `ReservationSmsAssignment`를 만들려고 할 수 있습니다.
- DB 제약 조건에 따라 실패하거나, 더 나쁘게는 테넌트 없는 데이터가 생길 수 있습니다.

수정 제안:

- `tenant_id is None`이면 명시적으로 실패
- 또는 `schedule.tenant_id`를 fallback으로 사용

개인적으로는 아래 방식이 안전합니다.

```text
current_tenant_id가 있으면 사용
없으면 schedule.tenant_id 사용
둘 다 없으면 RuntimeError
```

우선순위: 중간

## 3. "오늘 체크인 대상"만 보는 것이 맞는지 정책 확인 필요

위치: `backend/app/services/party3_mms.py`

현재 `reconcile_party3_mms()`는 아래 조건의 예약만 봅니다.

```text
Reservation.check_in_date == date
Reservation.status == CONFIRMED
party_type in ("2", "2차만")
```

즉, 이 MMS의 대상은 "오늘 체크인하는 2차 참여자"입니다.

문제는 실제 운영 의도가 아래 둘 중 무엇인지에 따라 대상자가 달라진다는 점입니다.

```text
정책 A: 오늘 체크인하는 2차 참여자에게만 보낸다
정책 B: 오늘 파티에 참여하는 2차 참여자 전체에게 보낸다
```

현재 코드는 정책 A입니다.

예외 상황:

```text
예약 A: 4월 21일 체크인 / 4월 23일 체크아웃
4월 22일 party_type = "2"
```

이 사람은 4월 22일에 숙박 중이고 2차 파티에 참여할 수 있습니다.

하지만 `check_in_date == "2026-04-22"`가 아니므로 현재 코드에서는 4월 22일 MMS 대상에서 제외됩니다.

현재 동작:

```text
연박/체류 중인 사람이라도 target_date에 체크인하지 않았으면 제외
```

이 동작이 맞는 경우:

- 이 MMS가 "체크인 당일 파티 안내"인 경우
- 체크인 당일에만 안내하면 충분한 운영 정책인 경우

이 동작이 틀릴 수 있는 경우:

- 이 MMS가 "오늘 2차 파티 참여자 안내"인 경우
- 연박자가 둘째 날에도 파티 참여를 신청할 수 있는 경우
- 날짜별 `ReservationDailyInfo.party_type`으로 당일 파티 참여를 관리하는 경우

수정 제안:

- 정책 A가 맞다면 현재 코드 유지
- 정책 B가 맞다면 대상 조건을 stay-coverage 기준으로 변경

정책 B의 예상 조건:

```text
check_in_date <= date < check_out_date
또는 check_in_date == date and check_out_date is null
```

그리고 `party_type`은 지금처럼 DailyInfo 값을 우선 사용하면 됩니다.

확인 질문:

```text
party3_today_mms는 "오늘 체크인한 2차 참여자"에게만 보내는 MMS가 맞나요?
아니면 "오늘 숙박 중이고 오늘 2차 파티에 참여하는 사람 전체"에게 보내야 하나요?
```

우선순위: 정책 확인 필요

## 삭제 가능 후보

## 삭제 후보 1. logger

위치: `backend/app/services/party3_mms.py`

현재 파일에는 logger가 선언되어 있습니다.

```python
logger = logging.getLogger(__name__)
```

하지만 현재 코드에서는 사용되지 않습니다.

삭제 가능:

- 지금 코드 기준으로는 삭제해도 동작 영향이 없습니다.

주의:

- 위에서 제안한 warning 로그를 추가할 계획이면 유지해도 됩니다.
- 예를 들어 템플릿 비활성, tenant context 없음, 중복 스케줄 감지 로그를 남길 거라면 logger가 필요합니다.

## 삭제 후보 2. logging import

위치: `backend/app/services/party3_mms.py`

`logger`를 삭제한다면 아래 import도 같이 삭제할 수 있습니다.

```python
import logging
```

삭제 가능:

- logger를 계속 쓰지 않는다면 삭제해도 됩니다.

## 삭제 후보 3. PARTY3_MMS_CUSTOM_TYPE 문자열 중복

위치:

- `backend/app/services/party3_mms.py`
- `backend/app/services/custom_schedule_registry.py`
- `backend/app/services/sms_sender.py`

`"party3_today_mms"` 문자열이 여러 파일에 반복됩니다.

현재 반복 위치:

```text
party3_mms.py
custom_schedule_registry.py
sms_sender.py
```

삭제라기보다는 통합 후보입니다.

수정 제안:

- 커스텀 스케줄 레지스트리를 단일 source of truth로 만들기
- 또는 별도 상수 모듈로 분리

예상 효과:

- 오타 위험 감소
- 새 MMS 타입 추가 시 수정 위치 감소

## 삭제 후보 4. PARTY3_TYPES 하드코딩

위치: `backend/app/services/party3_mms.py`

현재 대상 party_type은 코드에 고정되어 있습니다.

```python
PARTY3_TYPES = ("2", "2차만")
```

현재 프론트와 설정 화면도 `"2"`, `"2차만"`을 쓰고 있어서 지금은 맞아 보입니다.

다만 운영에서 party_type 표현이 바뀌면 코드 수정이 필요합니다.

삭제라기보다는 설정화 후보입니다.

수정 제안:

- 당장은 유지 가능
- 장기적으로는 설정값 또는 레지스트리 메타데이터로 이동 고려

## 결론

지금 당장 안전하게 삭제 가능한 것은 `logger`와 `logging import` 정도입니다.

다만 warning 로그를 추가할 계획이면 삭제하지 말고 활용하는 편이 낫습니다.

기능적으로 더 중요한 수정은 템플릿 비활성 상태와 tenant_id fallback 처리입니다.

---

# password_display.py 정리 제안

- `build_prefixed_password()`는 사실상 `room_assignment._resolve_prefixed_password()`의 마지막 분기에서만 쓰입니다.
- 표시용 비밀번호는 배정 생성 시 저장되는 값이므로 `room_assignment.py` 안의 `_build_prefixed_password()`로 옮기는 편이 자연스럽습니다.
- `templates/variables.py`로 옮기면 렌더링 때마다 랜덤 값이 바뀔 수 있어 비추천입니다.
- 추천 작업: 함수 이동/이름 변경 → `password_display.py` 삭제 → 단위 테스트 import 경로 수정.

---

# room_assignment_invariants.py 수정 메모

- 일반실 수동 복수배정이 미래 날짜에도 허용되는 정책이면, 현재 `check_assignment_validity()`의 일반실 이중배정 자동 위반 처리는 정책과 충돌합니다.
- 도미토리 성별 판단은 `Reservation.gender`보다 예약 상품 기준이 더 정확하므로, 상품 기준 성별 판별 공통 함수를 만들어 자동배정/수동배정/invariant에서 같이 쓰는 편이 안전합니다.
- `bed_capacity`는 `RoomUpdate`에서 `null` 입력 가능성이 있으므로, 도미토리는 API/DB에서 1 이상을 강제하고 런타임 fallback은 로그를 남기는 방식이 좋습니다.

---

# room_assignment.py 수정 제안

- 일반실 `booking_count > 1` 자동배정은 현재 `RoomAssignment(reservation_id, date)` 유니크 제약 때문에 여러 방이 아니라 마지막 방 하나만 남을 수 있습니다. 객실 수만큼 예약을 분리할지, 스키마를 바꿀지 정책 결정이 필요합니다.
- `reconcile_dates()`는 도미토리의 같은 방 기존 배정자를 충돌로 보고 미래 날짜면 밀어낼 수 있습니다. 일반실은 충돌 처리, 도미토리는 성별/상품/`bed_capacity` 초과만 검사하도록 분리하는 게 안전합니다.
- 도미토리 수동배정에서 기존 투숙자가 없으면 `new_count > bed_capacity` 검사가 스킵될 수 있습니다. `others` 유무와 관계없이 새 예약 인원 자체가 침대 수를 넘는지 먼저 검사해야 합니다.
- 도미토리 성별 기준은 `Reservation.gender`보다 예약 상품 기준이 정확하므로, 상품 기준 성별 판별 공통 함수를 `room_assignment.py`, `room_auto_assign.py`, `room_assignment_invariants.py`에서 같이 쓰는 편이 좋습니다.
- 일반실 수동 복수배정이 미래 날짜에도 허용되는 정책이면 현재 미래 충돌 push-out 로직과 충돌합니다. 당일/과거만 허용인지, 미래도 허용인지 정책을 고정해야 합니다.
- `assign_room()`에서 기존 도미토리 배정을 삭제한 뒤 기존 방의 `bed_order` compact가 빠져 있습니다. 방 이동 후 이전 도미토리의 침대 번호가 `1,3`처럼 비어 남을 수 있습니다.
- `unassign_room()`은 `section`을 바꾸지 않고 프론트가 별도 API로 변경합니다. 방 해제는 성공하고 section 변경이 실패하면 `RoomAssignment`는 없는데 `section='room'`인 상태가 생길 수 있어 한 트랜잭션으로 묶는 게 안전합니다.
- `check_capacity_all_dates()`는 도미토리 `bed_capacity=None`일 때 비교 에러가 날 수 있습니다. `room.bed_capacity or 1` fallback과 API/DB의 `bed_capacity >= 1` 검증이 필요합니다.
- `assigned_by`는 `"auto"`, `"manual"` 외 값이 들어와도 사실상 수동처럼 동작할 수 있습니다. enum 또는 명시 검증을 추가하는 게 좋습니다.
- 삭제 후보: `sync_denormalized_field()`는 deprecated이고 현재 실사용 호출이 없어 보입니다. 외부 스크립트 import만 확인 후 삭제 후보입니다.
- 삭제/이동 후보: `password_display.py`의 `build_prefixed_password()`는 `room_assignment.py` 내부 helper로 옮기고 import를 제거하는 방향이 자연스럽습니다.
- 리팩토링 후보: push-out 후처리, 인원 계산(`party_size or booking_count or 1`), 날짜별 충돌 정책이 여러 곳에 흩어져 있어 공통 helper로 통일하는 편이 안전합니다.

---

# room_lookup.py 수정 제안

이 문서는 `backend/app/services/room_lookup.py`를 기준으로, 현재 코드에서 수정하면 좋은 부분과 충돌이 우려되는 부분, 논리적으로 애매한 부분, 삭제 가능 여부와 중복 여부를 정리한 내용입니다.

## 핵심 요약

이 파일은 객실 배정 자체를 하는 파일이 아닙니다.

역할은 단순합니다.

```text
예약 여러 건의 room 정보를 한 번에 조회
→ N+1 쿼리 방지
→ API/스케줄러/미리보기에서 재사용
```

즉 `RoomAssignment`에 이미 저장된 객실 정보를 읽어와서,

- 예약 목록 API
- 파티 체크인 목록
- 문자 발송 대상 미리보기

같은 곳에서 빠르게 쓰게 해주는 조회 유틸입니다.

방향 자체는 좋고 파일도 작습니다.

다만 아래 문제는 정리할 가치가 있습니다.

- 주석과 실제 동작이 다름
- 날짜 없는 조회 의미가 애매함
- 호출부가 별도 보정 로직을 또 가지고 있음
- 얇은 wrapper 함수가 유지 가치 대비 단순함

## 1. 주석은 earliest assignment라고 하지만 실제 구현은 보장하지 않음

위치:

- `backend/app/services/room_lookup.py:16`
- `backend/app/services/room_lookup.py:27`
- `backend/app/services/room_lookup.py:31`

현재 docstring 은 아래처럼 읽힙니다.

```text
target_date가 없으면 예약별 가장 이른 assignment를 사용
```

하지만 실제 코드는:

```text
order_by 없음
query.all() 결과를 순서대로 순회
처음 본 assignment 하나만 채택
```

즉 "가장 이른 날짜"를 보장하지 않습니다.

연박 중 객실 이동이 있었거나,
DB가 다른 순서로 row를 반환하면 결과가 달라질 수 있습니다.

문제 예시:

```text
예약 A
4/10 → 101호
4/11 → 102호

target_date 없이 조회
→ 기대: 4/10 기준 101호
→ 실제: 우연히 102호가 먼저 오면 102호 가능
```

수정 제안:

- 진짜 earliest 정책이면 `order_by(RoomAssignment.date.asc(), RoomAssignment.id.asc())` 추가
- earliest가 아니라면 docstring을 실제 정책대로 수정

우선순위: 높음

## 2. target_date 없는 조회의 의미가 애매함

위치:

- `backend/app/services/room_lookup.py`

이 함수는 두 가지 모드를 섞어 가지고 있습니다.

```text
1. target_date 있음
   → 그 날짜의 객실 조회

2. target_date 없음
   → 대표 assignment 하나 조회
```

문제는 두 번째 의미가 너무 모호하다는 점입니다.

대표 assignment 가 아래 중 무엇인지 코드에서 명확하지 않습니다.

- 가장 이른 날짜
- 가장 최근 날짜
- 체크인 날짜
- 그냥 첫 row

이 모호함 때문에 호출부가 자기 필요에 맞는 보정 로직을 따로 갖게 됩니다.

예를 들어 예약 목록 API는 target_date 가 없을 때
"체크인 날짜 기준 room" 을 원해서 따로 보정하고 있습니다.

위치:

- `backend/app/api/reservations.py:299`

즉 현재 구조는:

```text
room_lookup.py 기본 정책이 충분히 명확하지 않다
→ 호출부가 추가 로직을 갖는다
→ 중복과 혼란이 생긴다
```

수정 제안:

- 함수 역할을 명확히 분리
  - `batch_room_lookup_for_date(...)`
  - `batch_room_lookup_for_checkin_date(...)`
  - 또는 `target_date` 없는 모드를 제거

우선순위: 높음

## 3. reservations.py 호출부에 중복 보정 로직이 있음

위치:

- `backend/app/api/reservations.py:303`
- `backend/app/api/reservations.py:311`

현재 `date` 없는 예약 목록 조회는 아래처럼 동작합니다.

```text
1. RoomAssignment를 직접 한 번 조회
2. check-in date와 맞는 reservation_id만 추림
3. 다시 batch_room_lookup() 호출
4. 다시 한 번 매핑
```

이건 조회 유틸을 쓰고 있는데도 호출부가 중복 계산을 하는 형태입니다.

즉 `room_lookup.py` 가 아래 요구를 충분히 직접 지원하지 못한다는 뜻입니다.

```text
예약별 check-in date 기준 room lookup
```

수정 제안:

- 이 로직을 `room_lookup.py` 안으로 옮겨 helper 함수로 분리
- 호출부는 단순히 함수 하나만 호출하게 정리

예상 효과:

- 예약 API 코드 단순화
- room lookup 정책이 한 군데로 모임
- 버그 수정 시 수정 위치 감소

우선순위: 중간에서 높음

## 4. 반환 타입이 너무 느슨함

위치:

- `backend/app/services/room_lookup.py:12`

현재 반환 타입은 `dict[int, dict]` 입니다.

이건 간단해서 쓰기 쉽지만, 구조가 고정돼 있는 함수치고는 너무 넓습니다.

실제 값 구조는 사실상 아래처럼 고정입니다.

```text
room_id
room_number
room_password
assigned_by
bed_order
```

문제는 호출부에서 키 이름 오타가 나도 타입 수준에서 잡기 어렵다는 점입니다.

수정 제안:

- `TypedDict` 나 별도 dataclass 사용 고려
- 최소한 docstring 에 반환 필드 전체를 더 명확히 적기

우선순위: 낮음에서 중간

## 5. room_password를 항상 같이 반환하는 것이 과한지 검토 필요

위치:

- `backend/app/services/room_lookup.py:49`

현재는 lookup 결과에 `room_password` 도 항상 들어갑니다.

문제는 이 함수가 광범위한 조회 유틸이라는 점입니다.

즉 사용처 중 일부는 단순히 아래만 필요합니다.

- 방 번호
- 배정 여부

그런데 비밀번호까지 항상 실어 나르면,

- 의미상 과도할 수 있고
- 나중에 다른 API에서 무심코 노출 범위를 넓힐 위험이 있습니다

지금 당장 취약점이라고 보기는 어렵지만,
유틸 함수가 너무 많은 정보를 기본값으로 주는 구조는 점검할 가치가 있습니다.

수정 제안:

- 필요 필드만 반환하는 별도 함수 분리
- 또는 password 포함 여부를 명시 옵션으로 받기

우선순위: 낮음

## 6. Room 조회에도 정책이 코드에 드러나지 않음

위치:

- `backend/app/services/room_lookup.py:40`

현재 `Room.id.in_(room_ids)` 로 단순 조회만 합니다.

대부분은 문제 없지만, 아래 정책이 코드상 명시돼 있지 않습니다.

- 비활성 방도 조회할 것인가
- 삭제 직전/legacy 데이터는 어떻게 볼 것인가

배정 기록의 source of truth가 `RoomAssignment` 라는 점을 생각하면,
이미 과거에 배정된 방이라면 비활성 room 이어도 조회하는 게 자연스럽습니다.

즉 이 부분은 "버그"라기보다,
정책이 암묵적이라는 점이 애매합니다.

수정 제안:

- docstring 또는 주석에 "과거 배정 기록 복원을 위해 Room.is_active 필터를 두지 않음" 같은 의도를 명시

우선순위: 낮음

## 7. batch_room_number_map()는 얇은 wrapper지만 실사용 가치는 있음

위치:

- `backend/app/services/room_lookup.py:56`
- `backend/app/api/party_checkin.py:124`
- `backend/app/scheduler/template_scheduler.py:619`

이 함수는 사실상 한 줄 wrapper 입니다.

```python
lookup = batch_room_lookup(...)
return {res_id: info["room_number"] or "" ...}
```

이런 함수는 종종 삭제 후보처럼 보일 수 있습니다.

하지만 현재는:

- 파티 체크인 API
- 템플릿 스케줄 미리보기

에서 의미 있게 쓰고 있어서, 당장 삭제할 정도는 아닙니다.

즉 판단은 아래 정도가 적절합니다.

```text
안전 삭제 후보는 아님
유지해도 무방
다만 팀이 helper 최소화를 원하면 통합 가능
```

우선순위: 낮음

## 삭제 가능 / 중복 여부 정리

### 삭제하면 안 되는 함수

- `batch_room_lookup()`
  - 핵심 유틸이고 실제 사용 중

- `batch_room_number_map()`
  - 매우 얇지만 실사용 중

### 삭제 후보라기보다 통합 후보

- `batch_room_number_map()`
  - 호출부에서 직접 `room_number`만 뽑게 바꿀 수는 있음
  - 하지만 현재 상태도 가독성 측면에서는 나쁘지 않음

### 실제 중복으로 보이는 부분

- `backend/app/api/reservations.py:299` 이하의 date 없는 보정 로직
  - 이건 `room_lookup.py` 정책이 애매해서 호출부가 중복 책임을 지는 상태로 보입니다.

## 추천 수정 순서

1. `target_date is None` 정책을 명확히 결정
2. docstring 과 실제 구현을 일치시키기
3. check-in date 기준 lookup helper 를 `room_lookup.py`로 이동
4. `reservations.py` 중복 보정 로직 정리
5. 필요하면 반환 타입과 password 노출 범위 다듬기

## 결론

이 파일은 구조가 작고 역할도 명확해서, 큰 구조적 문제를 가진 파일은 아닙니다.

오히려 핵심 문제는 "잘못 만들었다"기보다 아래에 가깝습니다.

```text
정책이 애매한 부분이 하나 있고
그 애매함을 호출부가 메우면서 중복이 생겼다
```

가장 먼저 손볼 것은 `target_date=None` 정책입니다.

이 부분만 명확해지면:

- 주석/구현 불일치 해소
- 예약 목록 API의 보정 로직 축소
- room lookup 관련 책임이 한 파일로 모임

이라는 정리가 가능합니다.
