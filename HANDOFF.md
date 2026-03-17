# HANDOFF

## Current [1773736337]
- **Task**: 파티만 태그 분리 리팩토링 + SMS 시스템 안정화 + 스태프 페이지
- **Completed**:
  - 알리고 SMS API 연동 완료 (실제 발송 동작 확인)
  - result_code 문자열 비교 수정, renderer key→template_key 수정
  - SMS toggle → 실제 발송 + skip_send + upsert(404 방지)
  - send_single_sms 공통 함수로 발송 로직 통합
  - SMS 발송 활동 로그 (전체 메시지 + 대상자 테이블)
  - sync_sms_tags filters 기반 매칭 (building/assignment)
  - N+1 Room 쿼리 해소 + 필터 일관성 테스트 5건
  - building/room_num 템플릿 변수 Room/Building 모델 기반
  - DEFAULT_CAPACITY 상품별 기본 인원
  - 타임존 통일 UTC/KST (16파일)
  - 스케줄러 detached instance 에러 수정 (클로저 → schedule_id 캡처)
  - 스태프 전용 파티 체크인 페이지 (사이드바 없음, party_type 필터)
  - 예약 삭제 cascade (FK 제약 해결)
  - 스케줄 활성화 시간 범위 (active_start_hour/active_end_hour)
  - 활동 로그 detail JSON 파싱 + UTC→KST + targets 테이블 표시
  - 성별 색상 진하게, 파티/성별 컬럼 순서 교체
- **Next Steps**:
  - 파티만 태그 분리 리팩토링 (진행 예정):
    - tags의 "파티만" → SMS 필터에서 제거
    - 파티존 판단: RoomAssignment 유무 + 섹션 위치로만
    - 출처 구분: naver_room_type에 통합 (수동추가/파티만)
    - 프론트 6곳 + 백엔드 8곳 수정
  - GUNICORN_WORKERS=1 설정 (중복 실행 방지)
  - 스태프 사이드바 제한 동작 확인
- **Blockers**: None
- **Related Files**:
  - `backend/app/services/room_assignment.py` — sync_sms_tags, _matches_filter_group
  - `backend/app/scheduler/template_scheduler.py` — FILTER_BUILDERS, execute_schedule
  - `frontend/src/pages/RoomAssignment.tsx` — 파티존 판단 로직 (tags 참조 6곳)
  - `backend/app/services/sms_sender.py` — send_single_sms
  - `frontend/src/pages/PartyCheckin.tsx` — 스태프 전용 페이지

## Past 1 [1773729796]
- **Task**: 알리고 SMS 연동 + 필드명 수정 + SMS 태그 시스템 개선 + 타임존 통일
- **Completed**: 알리고 연동, 필드명 수정, 건물관리 모달, SMS 통합 발송, 태그 필터 매칭, N+1 해소, 타임존 UTC 통일
- **Note**: commits f59e3c0~592f068

## Past 2 [1773678979]
- **Task**: 네이밍 컨벤션 v2 전체 리팩토링 + 스케줄 필터 UI 개선 + 템플릿 변수 통일
- **Completed**: 모델 필드 17건 리네이밍, ORM↔JSON 매핑 통일 8건, DEPRECATED 13건 삭제, 스케줄 필터 토글 UI
- **Note**: commit e80c20e
