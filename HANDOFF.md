# HANDOFF

## Current [1773333022]
- **Task**: 코드 정리 + SMS 태그 자동 관리 (sync_sms_tags) + 발송 확인 모달
- **Completed**:
  - 백엔드 dead code 대규모 정리
    - StorageProvider 완전 제거 (protocol, mock, real, factory 참조)
    - NotificationService: storage_provider 파라미터, start_row/end_row, 중복 _get_party_price_message 분기 통합
    - Reservation 모델: sheets_row_number, sheets_last_synced 컬럼 제거
    - TemplateRenderer.create_template() 미사용 메서드 제거
    - GenderStatsResponse 미사용 클래스 제거
    - GenderAnalyzer: StorageProvider 의존성 및 extract_gender_stats 메서드 제거
    - 미사용 import 정리 (get_db, BackgroundTasks)
    - 일회성 스크립트 삭제 (test_mock.py, verify_migration.py, setup_template_schedules.py)
  - 테스트/샘플 데이터 정리
    - mock/llm.py, mock/reservation.py, mock/data/ 삭제
    - rules.yaml 삭제 (engine.py에 파일 없을 때 graceful 처리 추가)
    - migrate_templates.py 삭제
  - 프론트엔드 dead code 정리
    - api.ts: 레거시 campaignsAPI 5개 메서드, genderStatsAPI, syncSheets, getById 제거
    - Templates.tsx: 미사용 Card, Alert import 제거
    - Reservations.tsx: 미사용 reservation_time 폼 상태 제거
    - RoomAssignment.tsx: raw api 호출 → smsAssignmentsAPI로 통일
    - index.css: 미사용 .contact-active, .room-cell-hover 클래스 제거
    - Messages.tsx: OUR_NUMBER, 빠른답변 템플릿 제거
  - sync_sms_tags 중앙 Sync 함수 구현
    - 예약 상태 변경 시 TemplateSchedule target_type 기반으로 태그 자동 재계산
    - assign_room, unassign_room, clear_all_for_reservation에서 호출
    - RoomAssignment 테이블 직접 조회 (비정규화 필드 불일치 문제 해결)
    - 발송 완료 태그(sent_at) 및 수동 할당 태그(assigned_by=manual) 보호
  - 프론트 낙관적 업데이트: 객실 배정 시 room_info 태그 즉시 표시, 해제 시 즉시 제거
  - SMS 발송 확인 모달 추가 (칩 클릭 시 발송/취소 양방향 확인)
  - SMS 태그 칩 정렬: 템플릿 ID 순서로 정렬
- **Next Steps**:
  - 레거시 campaigns 발송 시스템 (send_room_guide, send_party_guide) 정리/제거
  - room_sms_sent, party_sms_sent 레거시 플래그 제거 → ReservationSmsAssignment로 완전 이관
  - 야간 재배정(room_reassign.py) 처리 방식 결정
  - template_scheduler.py의 auto_assign_for_schedule를 sync_sms_tags 기반으로 통합 검토
- **Blockers**: None
- **Related Files**:
  - `backend/app/services/room_assignment.py` - sync_sms_tags, _reservation_matches_schedule 추가
  - `frontend/src/pages/RoomAssignment.tsx` - 발송 확인 모달, 낙관적 업데이트, 태그 정렬
  - `backend/app/analytics/gender_analyzer.py` - StorageProvider 의존성 제거
  - `backend/app/notifications/service.py` - storage_provider, start_row/end_row 제거
  - `frontend/src/services/api.ts` - 레거시 API 메서드 대규모 정리

## Past 1 [1773329524]
- **Task**: 객실배정 페이지 UX 개선 + 발송 로직 태그 기반 통일 + DEMO_MODE 변경
- **Completed**: SMS 칩 토글 방식, 낙관적 업데이트, 태그 기반 발송 통일, DEMO_MODE SMS only, StorageProvider 제거
- **Note**: sms-send-by-tag 엔드포인트 추가, stat 카드 성별 색상 적용

## Past 2 [1773221294]
- **Task**: 객실 배정 시스템 단순화 계획 + SMS 타겟팅 수정
- **Completed**: SMS 스케줄 get_targets room_assigned 수정, auto_assign_for_schedule 수정, 객실 배정 시스템 전체 분석
- **Note**: RoomAssignment JOIN → Reservation.room_number IS NOT NULL로 변경
