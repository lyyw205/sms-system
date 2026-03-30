# HANDOFF

## Current [1774833840]
- **Task**: 멀티테넌트 격리 검증 파이프라인 (ooo-tenant-check) 전체 실행
- **Completed**:
  - **분석**: 5개 전문가 에이전트 병렬 실행 (데이터 격리, API, 스케줄러, 인증/캐시, DB 스키마)
  - **Phase 1 (CRITICAL 6건)**: `.update()` tenant_id 누락 4곳(rooms.py), reconcile_dates 필터(room_assignment.py), JOIN tenant 동등(naver_sync.py, room_auto_assign.py), consecutive_stay tenant 가드, deps.py fail-closed 인증
  - **Phase 2 (HIGH 5건)**: Scheduler API 크로스테넌트 차단(scheduler.py), filters.py building JOIN, sms_sender.py JOIN, schedule_manager.py Phase1/2 bypass 분리, room_auto_assign None 가드
  - **Phase 3 (MEDIUM 3건)**: 활동로그 소스 라벨 조건부(unstable 있을 때만 [스테이블]), event_bus publish tenant_id 필수화, bypass_tenant_filter reset nested try/finally 4곳
- **Next Steps**:
  - M4: UniqueConstraint에 tenant_id 추가 (5개 모델) — Alembic 마이그레이션 필요, PostgreSQL 전환 시 처리
  - C5: load_template_schedules bypass 범위 축소 — ScheduleManager 구조 변경 필요
  - 언스테이블 네이버 쿠키 재입력 (만료됨)
  - 실제 동기화 테스트
- **Blockers**: None
- **Related Files**:
  - `backend/app/api/rooms.py` — C1: .update() tenant_id 추가
  - `backend/app/api/deps.py` — C7: fail-closed 인증
  - `backend/app/api/scheduler.py` — H5: 크로스테넌트 Job 제어 차단
  - `backend/app/scheduler/jobs.py` — M1/M3: 로그 라벨 + bypass reset
  - `backend/app/scheduler/schedule_manager.py` — H6: Phase1/2 bypass 분리
  - `backend/app/services/naver_sync.py` — C3: JOIN tenant 동등
  - `backend/app/services/room_auto_assign.py` — C4/H7: JOIN + None 가드
  - `backend/app/services/consecutive_stay.py` — C6: tenant_id 파라미터
  - `backend/app/services/filters.py` — H1: building JOIN tenant 동등
  - `backend/app/services/sms_sender.py` — H3: JOIN tenant 동등
  - `backend/app/services/event_bus.py` — M2: tenant_id 필수화
  - `backend/app/services/room_assignment.py` — C2: reconcile_dates tenant_id

## Past 1 [1774800841]
- **Task**: 언스테이블 파티 업체 통합 (Phase 0~7 + 추가 수정)
- **Completed**: DB 스키마, Settings UI, 네이버 동기화 source 분기, 객실배정 언스테이블 행, 컨텍스트 메뉴 복사, 통계 카드, 템플릿 스케줄 필터, 파티 체크인 탭 분리, 보라색 점, 테넌트별 UI 격리
- **Note**: commits daca540, c09a06a, ec7bbba

## Past 2 [1774678131]
- **Task**: Timezone 통일 + 코드 잔재 정리 + 스킬 업그레이드
- **Completed**: today_kst() 헬퍼, 17곳 KST 교체, normalizeUtcString() 유틸, 죽은 코드 -74줄, 스킬 3개 교차검증 추가
- **Note**: commits 71fcefb, 07ce15e
