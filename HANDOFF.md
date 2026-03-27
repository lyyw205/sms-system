# HANDOFF

## Current [1774619519]
- **Task**: 도미토리 bed_order + 커스텀 드래그 전환 + UX 개선 + SMS 테스트 데이터
- **Completed**:
  - **bed_order 도입** (도미토리 행 순서 날짜간 통일)
    - `RoomAssignment.bed_order` 컬럼 + auto-migration
    - `_compute_bed_order()`: 전날 같은 방 reservation_id/stay_group_id → bed_order 상속, 없으면 빈 슬롯
    - `batch_room_lookup` → API 응답에 bed_order 전달
    - 프론트엔드: 20줄 정렬 로직 → 2줄 `bed_order` 기준 정렬
  - **HTML5 드래그 → 커스텀 포인터 드래그 전환**
    - pointer events 기반 (wheel 스크롤 + 터치 지원)
    - `data-drop-zone` + `elementFromPoint`로 드롭 타겟 판별
    - 가장자리 자동 스크롤 (80px edge zone)
  - **UX 개선**
    - sticky 날짜 헤더 + 테이블 헤더 (ResizeObserver 동적 측정)
    - 그룹 stripe 배경색 (groupIndex 기준 교대)
    - 구분선 1px 통일 (방 border-b 색상 교체 방식)
    - 구분선 모달: 첫행 위/마지막행 아래 추가 가능
    - 메모 컬럼 텍스트 색상 → primary black
    - z-index 정리 (sticky 헤더 < 드롭다운)
  - **SMS 테스트 예약자 생성** (STABLE 테넌트)
    - 11건 생성 (전화번호 01036886080 통일)
    - 18개 활성 스케줄의 모든 필터 조합 커버
    - 연박 2박(J) + 연장자 체인(K1/K2) + stay_filter=exclude 테스트
    - 객실 배정 완료 (본관/로하스/펠리체)
    - 노션 체크리스트 생성 (3/28~4/4 날짜별 수신/미수신 28건)
  - **Click-Select 전환 계획서 작성** (`.omc/plans/click-select-migration.md`)
    - 드래그/선택 토글 모드 설계 (v2)
    - 기존 드래그 유지 + 선택 모드 독립 추가 (~140줄)
    - change-validator 검증 완료 (5건 반영)
  - **잔재 정리**: Card import 삭제
- **Next Steps**:
  - 드래그/선택 토글 모드 구현 (계획서 `.omc/plans/click-select-migration.md`)
  - SMS 테스트 실행 (3/28부터 매일 체크리스트 확인)
  - TODO #1: ParticipantSnapshot 시간대별 갱신
  - TODO #5: 모바일 버튼 레이아웃 정리
  - TODO #6: PWA 설정 (iOS 탭 전환 방지)
- **Blockers**: None
- **Related Files**:
  - `backend/app/db/models.py` — RoomAssignment.bed_order 컬럼
  - `backend/app/services/room_assignment.py` — _compute_bed_order()
  - `backend/app/services/room_lookup.py` — bed_order API 전달
  - `backend/app/api/reservations.py` — bed_order 응답 스키마
  - `frontend/src/pages/RoomAssignment.tsx` — 커스텀 드래그 + sticky + UX
  - `.omc/plans/click-select-migration.md` — 토글 모드 구현 계획서

## Past 1 [1774603943]
- **Task**: SMS 칩 배정 로직 통합 + column_match AND 수정 + 도미토리 인원수 버그 수정 + 객실 그룹 UX 개선
- **Completed**: chip_reconciler 통합, column_match AND 수정, 네이버 API USEDATE 수정, sync reconcile_date 파라미터, is_long_stay 리팩토링, dead code 정리, 미사용 import 14개, 객실 그룹 구분선 UX
- **Note**: commits a2da705..432318f

## Past 2 [1774540510]
- **Task**: 모바일 반응형 디자인 + 연박 수동 묶기/해제 + 로그인 저장
- **Completed**: 모바일 반응형 (Layout/Dashboard/Reservations/RoomSettings/Templates/ActivityLogs), 연박 묶기/해제 UI, 예약자 추가 버튼 복원, 로그인 저장
- **Note**: 객실배정은 PC와 동일 가로스크롤 방식으로 결정
