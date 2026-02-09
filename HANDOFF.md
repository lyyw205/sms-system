# HANDOFF

## Current [1770613489]
- **Task**: SMS 예약 시스템 초기 설정 및 독립적인 캠페인 시스템 구현
- **Completed**:
  - 백엔드/프론트엔드 서버 실행 환경 구성 (Python venv, npm 의존성 설치)
  - 데이터베이스 초기화 및 시드 데이터 생성 (SQLite 모드)
  - CLAUDE.md 프로젝트 가이드 문서 작성
  - 독립적인 캠페인 시스템 구현 (백엔드 API + 프론트엔드 UI)
    - 각 캠페인이 독립적으로 대상 + 메시지 정의 포함
    - API: GET /campaigns/list, POST /campaigns/send, GET /campaigns/preview
    - 캠페인 타입: tag_객후, tag_1초, tag_2차만, sms_room, sms_party, template_welcome 등
  - 예약 관리 페이지를 파티 신청자 관리로 재구성
    - 날짜별 필터링, 성별/인원 통계 표시
    - 태그 기반 신청자 관리 (1초, 2차만, 객후 등)
  - 객실 배정 페이지의 캠페인 선택 UI 단일 Select로 통합
  - anthropic 패키지 버전 충돌 해결 (0.8.1 → >=0.16.0)
- **Next Steps**:
  - 프론트엔드 에러 디버깅 (파티 신청자 목록 로드 실패 확인 필요)
  - 캠페인 발송 기능 테스트
  - 각 캠페인별 템플릿 메시지 정의
  - Real Provider 구현 (프로덕션 모드 전환 시)
- **Blockers**: 프론트엔드에서 "파티 신청자 목록 로드 실패" 에러 발생 (백엔드는 정상 동작 중)
- **Related Files**:
  - `/home/iamooo/repos/sms-reservation-system/CLAUDE.md`
  - `/home/iamooo/repos/sms-reservation-system/backend/app/api/campaigns.py`
  - `/home/iamooo/repos/sms-reservation-system/backend/requirements.txt`
  - `/home/iamooo/repos/sms-reservation-system/frontend/src/pages/Reservations.tsx`
  - `/home/iamooo/repos/sms-reservation-system/frontend/src/pages/RoomAssignment.tsx`
  - `/home/iamooo/repos/sms-reservation-system/frontend/src/services/api.ts`
