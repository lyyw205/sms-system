# E2E 테스트 계획서

SMS 예약 시스템 핵심 기능 E2E 테스트 항목.
Playwright MCP를 사용하여 로컬 서버에서 실행하며, 테스트 후 DB를 원복한다.

## 핵심 검증 목표

1. 네이버 예약을 통해 들어오는 예약자들이 잘 분리되고 저장되는지
2. 각 예약자에 알맞은 문자 발송 로직이 이행되는지

---

## A. 네이버 예약 동기화

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| A-1 | 신규 예약 동기화 | DB에 예약 생성, 필드 정확성 (이름, 전화, 체크인/아웃, 인원수) |
| A-2 | 기존 예약 업데이트 | 상태/날짜/인원 변경 시 DB 반영 |
| A-3 | 취소된 예약 동기화 | status=CANCELLED 반영 |
| A-4 | 중복 동기화 방지 | 같은 external_id 두 번 동기화 → 1건만 존재 |
| A-5 | reconcile 모드 (당일 포함) | 당일 예약도 재동기화 |

## B. 예약자 분류 (1박/연박/연장)

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| B-1 | 1박자 판별 | check_out - check_in == 1일 → is_long_stay=false |
| B-2 | 연박자 판별 (2박+) | check_out - check_in > 1일 → is_long_stay=true |
| B-3 | 연장자 감지 (동명+동번호+연속날짜) | A.checkout == B.checkin → 같은 stay_group_id |
| B-4 | 연장자 감지 (visitor_name 매칭) | visitor_name + phone 조합으로도 연결 |
| B-5 | 연장자 감지 (visitor_phone 매칭) | customer_name + visitor_phone 조합으로도 연결 |
| B-6 | 연장자 3건 이상 체인 | A→B→C 연속 → 모두 같은 group_id, order=0,1,2 |
| B-7 | is_last_in_group 정확성 | 마지막 예약만 true |
| B-8 | 연장자 해제 (중간 예약 취소) | B 취소 → A,C 그룹 해제, is_long_stay 재계산 |
| B-9 | 연박자+연장자 통합 변수 | 둘 다 is_long_stay=true로 통합 |
| B-10 | 1박 연장자 (1박×3건 연속) | 개별은 1박이지만 연결 후 is_long_stay=true |

## C. 객실 자동 배정

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| C-1 | biz_item 매핑 기반 자동 배정 | naver_biz_item_id → 매핑된 Room에 배정 |
| C-2 | 일반실 중복 배정 방지 | 같은 날짜 같은 방에 2명 배정 불가 |
| C-3 | 도미토리 용량 체크 | bed_capacity 초과 시 배정 실패 |
| C-4 | 도미토리 성별 잠금 | 남자 있는 방에 여자 배정 차단 |
| C-5 | 연박자 전 날짜 배정 | 3박 → 3일 모두 같은 방 배정 |
| C-6 | 연장자 같은 방 유지 | stay_group 멤버 → 이전 멤버와 같은 방 |
| C-7 | 성별 우선순위 정렬 | male_priority/female_priority에 따른 방 순서 |
| C-8 | 수동 배정 보호 | assigned_by='manual' → 자동 배정이 덮어쓰지 않음 |
| C-9 | party 섹션 제외 | section='party' → 자동 배정 대상 아님 |
| C-10 | 배정 후 denormalized 필드 | reservation.room_number, room_password 정확성 |

## D. 수동 객실 배정

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| D-1 | 단일 날짜 배정 | 특정 날짜만 방 배정 |
| D-2 | apply_subsequent (이후 전체) | 체크아웃까지 모든 날짜에 배정 |
| D-3 | apply_group (그룹 전체) | stay_group 전체 멤버에게 같은 방 |
| D-4 | 비도미토리 중복 차단 | 이미 배정된 방에 다른 예약 → 에러 |
| D-5 | 방 이동 로그 | 이전 방 → 새 방 ActivityLog 기록 |
| D-6 | 배정 해제 | room_id=null → RoomAssignment 삭제 |
| D-7 | 배정 후 SMS 칩 동기화 | sync_sms_tags 호출 → 칩 생성/삭제 |

## E. SMS 템플릿 스케줄 — schedule_type별

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| E-1 | daily 스케줄 | 매일 지정 시간에 트리거 |
| E-2 | weekly 스케줄 | 지정 요일에만 트리거 |
| E-3 | hourly 스케줄 | 매시 지정 분에 트리거 |
| E-4 | interval 스케줄 | N분 간격 트리거 |
| E-5 | interval + active_hours | 활성 시간대 내에서만 트리거 |
| E-6 | event 스케줄 (예약 시점) | hours_since_booking 내 예약에만 발송 |
| E-7 | event + expires_after_days | 만료일 이후 자동 비활성화 |

## F. SMS 스케줄 — target_mode별

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| F-1 | once + 1박자 | 체크인 당일 1회만 |
| F-2 | once + 연박자 (3박) | 체크인 당일 1회만 (중복 없음) |
| F-3 | once + 연장자 | 그룹 전체에서 1회만 (once_per_stay) |
| F-4 | daily + 1박자 | 체크인 당일 1회 (=once와 동일) |
| F-5 | daily + 연박자 (3박) | 3일 각각 칩 생성 + 발송 |
| F-6 | daily + 연장자 (1박×3) | 각 멤버의 체류일마다 칩 |
| F-7 | last_day + 1박자 | 체크아웃 전날 = 체크인일에 발송 |
| F-8 | last_day + 연박자 (3박) | 체크아웃 전날(3일차)에만 발송 |
| F-9 | last_day + 연장자 | is_last_in_group=true인 멤버만, 마지막 날에만 |

## G. SMS 스케줄 — date_target별

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| G-1 | today (오늘 체크인) | 오늘 체크인 예약만 대상 |
| G-2 | tomorrow (내일 체크인) | 내일 체크인 예약만 대상 |
| G-3 | today_checkout (오늘 체크아웃) | 오늘 체크아웃 예약만 대상 |
| G-4 | tomorrow_checkout (내일 체크아웃) | 내일 체크아웃 예약만 대상 |

## H. SMS 스케줄 — 구조적 필터별

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| H-1 | assignment=room | section='room'인 예약만 |
| H-2 | assignment=party | section='party'인 예약만 |
| H-3 | assignment=unassigned | section='unassigned'인 예약만 |
| H-4 | building 필터 | 해당 건물에 배정된 예약만 |
| H-5 | room 필터 | 해당 방에 배정된 예약만 |
| H-6 | building + unassigned 혼합 | 미배정자도 포함되는지 |
| H-7 | column_match: contains | party_type에 "1차" 포함 |
| H-8 | column_match: not_contains | party_type에 "1차" 미포함 |
| H-9 | column_match: is_empty | notes가 비어있는 예약 |
| H-10 | column_match: is_not_empty | notes가 있는 예약 |
| H-11 | 복합 필터 (AND) | building=1 AND assignment=room |
| H-12 | 동일 타입 복수 (OR) | building=1 OR building=2 |
| H-13 | party_type 일별 오버라이드 | ReservationDailyInfo 우선 적용 |

## I. SMS 스케줄 — stay_filter / once_per_stay

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| I-1 | stay_filter=null (전체) | 1박+연박+연장 모두 대상 |
| I-2 | stay_filter=exclude | 1박자만 대상, 연박/연장 제외 |
| I-3 | once_per_stay=false | 그룹 멤버 각각 발송 |
| I-4 | once_per_stay=true + 연장자 | 그룹 중 earliest만 발송 |
| I-5 | once_per_stay=true + 연박자 | 중복 발송 방지 |
| I-6 | stay_filter=exclude + once_per_stay | 1박자만 + 중복 방지 |

## J. SMS 스케줄 — send_condition (성비 조건)

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| J-1 | 조건 충족 (gte) | male/female >= threshold → 발송 |
| J-2 | 조건 미충족 (gte) | male/female < threshold → 미발송 |
| J-3 | 조건 충족 (lte) | male/female <= threshold → 발송 |
| J-4 | female=0 처리 | ratio=∞ → gte는 항상 true |
| J-5 | 양쪽 0명 | 발송 안 함 |
| J-6 | send_condition_date=today vs tomorrow | 각각 해당 날짜 기준 |

## K. SMS 스케줄 — event 카테고리 전용

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| K-1 | hours_since_booking 내 예약 | 시간 내 확정 예약 → 발송 |
| K-2 | hours_since_booking 초과 | 시간 초과 → 미발송 |
| K-3 | gender_filter=female | 여성 예약만 대상 |
| K-4 | gender_filter=male | 남성 예약만 대상 |
| K-5 | max_checkin_days | 체크인 N일 이내만 대상 |
| K-6 | event + stay_filter=exclude | 이벤트 + 1박자만 |

## L. 칩 (ReservationSmsAssignment) 생성/삭제

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| L-1 | 스케줄 생성 → 칩 자동 생성 | 대상자에게 칩 즉시 생성 |
| L-2 | 스케줄 수정 → 칩 재조정 | 필터 변경 시 기존 칩 삭제 + 새 칩 생성 |
| L-3 | 스케줄 비활성화 → 칩 삭제 | 미발송 칩만 삭제 |
| L-4 | 발송 완료 칩 보호 | sent_at 있는 칩 절대 삭제 안 됨 |
| L-5 | 수동 배정 칩 보호 | assigned_by='manual' 칩 삭제 안 됨 |
| L-6 | 수동 제외 칩 보호 | assigned_by='excluded' 칩 재생성 안 됨 |
| L-7 | 객실 배정 변경 → 칩 재동기화 | 방 변경 시 building/room 필터 반영 |
| L-8 | 예약 취소 → 칩 처리 | CANCELLED 예약의 칩 |
| L-9 | once 모드 칩 (체크인일만) | 1개 날짜에만 칩 |
| L-10 | daily 모드 칩 (전체 체류일) | 체류일 수만큼 칩 |
| L-11 | last_day 모드 칩 | 마지막 날에만 칩 |
| L-12 | exclude_sent (이중발송 방지) | 이미 sent된 템플릿+날짜 → 재대상 안 됨 |

## M. 칩 → UI 표시 (객실 배정 페이지)

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| M-1 | 대상자에게 칩 표시 | 칩 있는 예약자에게 해당 템플릿 칩 렌더링 |
| M-2 | 비대상자 칩 없음 | 필터에 안 맞는 예약자에게 칩 없음 |
| M-3 | 발송 완료 칩 상태 표시 | sent_at 있으면 발송완료 스타일 |
| M-4 | 미발송 칩 상태 표시 | sent_at 없으면 대기 스타일 |
| M-5 | 제외 칩 상태 표시 | excluded 상태 표시 |
| M-6 | 객실 배정 → 칩 추가 | room 필터 스케줄: 배정하면 칩 생김 |
| M-7 | 객실 해제 → 칩 제거 | room 필터 스케줄: 해제하면 칩 사라짐 |
| M-8 | building 변경 → 칩 변경 | 다른 건물로 이동 → 칩 재조정 |
| M-9 | section 변경 → 칩 변경 | party→room 변경 시 칩 재조정 |
| M-10 | 연박자 daily 칩 날짜별 표시 | 3박이면 각 날짜에 칩 1개씩 (총 3개 분산) |

## N. SMS 실제 발송

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| N-1 | 스케줄 트리거 → 발송 | 시간 도달 시 대상자에게 SMS 발송 |
| N-2 | 템플릿 변수 치환 | {{customer_name}}, {{room_num}} 등 정확 치환 |
| N-3 | 객실 비밀번호 생성 | room_password 자동 생성 또는 고정값 |
| N-4 | 인원수 버퍼 적용 | participant_buffer, gender_ratio_buffers 정확 계산 |
| N-5 | 반올림 (ceil/round/floor) | round_unit + round_mode 정확 적용 |
| N-6 | SMS/LMS 자동 감지 | 90바이트 이하→SMS, 초과→LMS |
| N-7 | 발송 후 칩 sent_at 업데이트 | 발송 성공 → timestamp 기록 |
| N-8 | 발송 실패 처리 | API 에러 시 칩 sent_at 그대로 null |
| N-9 | ActivityLog 기록 | 발송 결과 로그 (success/failed count) |
| N-10 | SSE 이벤트 발행 | 발송 후 실시간 이벤트 전파 |

## P. 인증/권한

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| P-1 | 로그인 성공 | JWT access + refresh 토큰 발급 |
| P-2 | 토큰 갱신 | refresh 토큰으로 access 재발급 |
| P-3 | SUPERADMIN 전체 접근 | 모든 API 접근 가능 |
| P-4 | STAFF 제한 접근 | 파티 체크인만 접근 |
| P-5 | 만료 토큰 거부 | 401 반환 |

## Q. 멀티테넌트 격리

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| Q-1 | 예약 데이터 격리 | 테넌트A 예약이 테넌트B에서 조회 안 됨 |
| Q-2 | 객실/건물 격리 | 테넌트A 방/건물이 테넌트B에 안 보임 |
| Q-3 | 템플릿 격리 | 테넌트A 템플릿이 테넌트B에 안 보임 |
| Q-4 | 스케줄 격리 | 테넌트A 스케줄이 테넌트B에 안 보임 |
| Q-5 | SMS 이력 격리 | 테넌트A 발송 이력이 테넌트B에 안 보임 |
| Q-6 | 칩(SmsAssignment) 격리 | 테넌트A 칩이 테넌트B에 안 보임 |
| Q-7 | ActivityLog 격리 | 테넌트A 로그가 테넌트B에 안 보임 |
| Q-8 | 파티 체크인 격리 | 테넌트A 체크인이 테넌트B에 안 보임 |
| Q-9 | 자동응답 규칙 격리 | 테넌트A 규칙이 테넌트B에 안 보임 |
| Q-10 | INSERT 자동 tenant_id 주입 | 어떤 모델이든 생성 시 현재 테넌트 자동 부여 |
| Q-11 | 스케줄 실행 시 격리 | 테넌트A 스케줄이 테넌트B 예약에 발송 안 함 |
| Q-12 | 동기화 시 격리 | 테넌트A 네이버 동기화가 테넌트B에 영향 없음 |
| Q-13 | 자동 배정 시 격리 | 테넌트A 자동배정이 테넌트B 방 사용 안 함 |
| Q-14 | SSE 이벤트 격리 | 테넌트A 이벤트가 테넌트B 구독자에게 안 감 |

## R. 파티 체크인

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| R-1 | 체크인 토글 ON | PartyCheckin 레코드 생성 |
| R-2 | 체크인 토글 OFF | 레코드 삭제 |
| R-3 | 날짜별 체크인 현황 | 특정 날짜의 체크인 목록 |

## S. 대시보드

| # | 테스트 항목 | 검증 포인트 |
|---|-----------|-----------|
| S-1 | 통계 카드 정확성 | 예약수, 발송수, 체크인수 등 |
| S-2 | 성별 통계 | male_count/female_count 정확 |
| S-3 | 날짜별 필터링 | 날짜 변경 시 통계 갱신 |

---

## 테스트 실행 환경

- **서버**: 로컬 (backend: uvicorn, frontend: npm run dev)
- **DB**: SQLite (DEMO_MODE=true)
- **SMS**: Aligo testmode=true (실제 발송 안 됨)
- **도구**: Playwright MCP (실제 브라우저 조작 + 스크린샷)
- **원복**: `rm sms.db && python -m app.db.seed`

## 총 테스트 항목 수

| 섹션 | 항목 수 |
|------|--------|
| A. 네이버 예약 동기화 | 5 |
| B. 예약자 분류 | 10 |
| C. 객실 자동 배정 | 10 |
| D. 수동 객실 배정 | 7 |
| E. 스케줄 type별 | 7 |
| F. 스케줄 target_mode별 | 9 |
| G. 스케줄 date_target별 | 4 |
| H. 스케줄 구조적 필터별 | 13 |
| I. 스케줄 stay_filter | 6 |
| J. 스케줄 send_condition | 6 |
| K. 스케줄 event | 6 |
| L. 칩 생성/삭제 | 12 |
| M. 칩 UI 표시 | 10 |
| N. SMS 실제 발송 | 10 |
| P. 인증/권한 | 5 |
| Q. 멀티테넌트 격리 | 14 |
| R. 파티 체크인 | 3 |
| S. 대시보드 | 3 |
| **합계** | **140** |
