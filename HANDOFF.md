# HANDOFF

## Current [1770619455]
- **Task**: 통합 게스트 관리 시스템 구현 및 객실 관리 기능 추가
- **Completed**:
  - 파티만 게스트 섹션을 객실 배정 페이지에 통합
    - 객실 게스트와 파티만 게스트를 하나의 페이지에서 관리
    - 드래그 앤 드롭으로 파티만 ↔ 객실 게스트 전환 가능
    - 파티만 게스트 CRUD 기능 (추가, 수정, 삭제)
  - 예약 객실 추적 기능 구현
    - room_info 필드: 최초 예약한 객실 타입 유지 (배정 변경 시에도 보존)
    - 객실 업그레이드 추적 가능 (예: 트윈룸 예약 → 패밀리룸 배정)
  - 객실 관리 시스템 구축
    - 별도 페이지(/rooms/manage)로 객실 추가/수정/삭제
    - 드래그 앤 드롭으로 객실 정렬 순서 변경
    - 객실명 중복 허용 (같은 번호, 다른 타입 가능)
    - 동적 객실 로드: 객실 배정 페이지에서 API로 객실 목록 불러오기
  - 인라인 편집 기능 추가
    - 객실/파티만 게스트 행에서 직접 수정 가능
    - 모달 없이 행 자체가 입력란으로 전환
    - 저장/취소 버튼으로 즉시 반영
  - SMS 발송 추적 시스템 구현
    - sent_sms_types 필드로 발송 이력 관리
    - 회색 태그(예정), 초록 태그(완료) 구분
    - 태그 클릭으로 발송 완료 전환
    - 중복 발송 방지: 객후, 파티안내, 객실안내 등
    - 조건부 태그 표시: 메모의 "객후", 객실 배정, 파티 참여 여부 등
- **Next Steps**:
  - SMS 캠페인 발송 시 sent_sms_types 자동 업데이트 통합
  - 발송 이력 기반 중복 발송 필터링 구현
  - 대시보드에 발송 통계 추가
  - 실제 SMS API 연동 (프로덕션 모드)
- **Blockers**: None
- **Related Files**:
  - `/home/iamooo/repos/sms-reservation-system/frontend/src/pages/RoomAssignment.tsx`
  - `/home/iamooo/repos/sms-reservation-system/frontend/src/pages/RoomManagement.tsx`
  - `/home/iamooo/repos/sms-reservation-system/backend/app/db/models.py`
  - `/home/iamooo/repos/sms-reservation-system/backend/app/api/rooms.py`
  - `/home/iamooo/repos/sms-reservation-system/backend/app/api/reservations.py`
  - `/home/iamooo/repos/sms-reservation-system/frontend/src/services/api.ts`

## Past 1 [1770613489]
- **Task**: SMS 예약 시스템 초기 설정 및 독립적인 캠페인 시스템 구현
- **Completed**: 백엔드/프론트엔드 환경 구성, 독립 캠페인 시스템, 파티 신청자 관리 페이지 재구성
- **Note**: CLAUDE.md 프로젝트 가이드 작성, anthropic 패키지 버전 충돌 해결
