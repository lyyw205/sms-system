# HANDOFF

## Current [1774345481]
- **Task**: Flowbite → shadcn/ui 완전 마이그레이션 + 반응형 디자인 계획 수립
- **Completed**:
  - 전체 12개 페이지 Playwright 스크린샷 캡처 + 디자인 시스템 문서 작성 (`docs/DESIGN_SYSTEM.md`)
  - **Flowbite → shadcn/ui 마이그레이션 완료** (Phase 1-7)
    - 16개 커스텀 컴포넌트 생성 (`components/ui/`)
    - 12개 페이지 + Layout.tsx 전체 교체 (import만 변경, JSX 변경 없음)
    - `FlowbiteTheme.tsx` 삭제 (204줄 오버라이드 제거)
    - `flowbite-react` + `@base-ui/react` 패키지 제거
    - 미사용 CSS 94줄 정리 (Flowbite hack, toss 변수, shadcn 토큰)
    - `tailwind-merge` 커스텀 font-size 그룹 등록 (text-white 충돌 방지)
  - **반응형 디자인 개선 계획 수립** (Architect + Critic 3자 합의)
    - Phase 1: 테이블 모바일 UX (패딩, sticky 열, 행 높이)
    - Phase 2: 레이아웃 + 타이포 (필터 바, 모달, 헤더)
    - Phase 3: Messages 1-panel 모바일
    - Phase 4: 터치 친화 미세조정
- **Next Steps**:
  - Phase 1 실행: table.tsx 패딩 반응형 + sticky 첫 열 + section-card overflow 수정
  - Phase 2 실행: 페이지 헤더/필터 바 모바일 스택 + Dashboard 성별 grid 수정
  - Phase 3 실행: Messages 연락처↔채팅 전환
  - Phase 4 실행: 터치 타겟 + 스크롤바
- **Blockers**: None
- **Related Files**:
  - `.omc/plans/responsive-design-plan.md` — 반응형 계획 (승인됨)
  - `docs/DESIGN_SYSTEM.md` — 디자인 시스템 문서
  - `docs/screenshots/` — 원본 페이지 스크린샷
  - `frontend/src/components/ui/` — shadcn 커스텀 컴포넌트 16개
  - `frontend/src/components/Layout.tsx` — 순수 HTML/Tailwind 레이아웃 (Flowbite 제거)
  - `frontend/src/lib/utils.ts` — cn() + extendTailwindMerge
  - `frontend/src/index.css` — 정리된 Toss 디자인 토큰
  - `frontend/components.json` — shadcn 설정

## Past 1 [1774317239]
- **Task**: 프로젝트 전체 감사 + 3단계 리팩토링 (중복 코드 / 변수명 일관성 / 구조 개선)
- **Completed**: Phase 1-3 완료 — 데드 코드 삭제, 7건 중복 해소, 구조 분리 (filters.py, room_lookup.py)
- **Note**: Commits `5e175d4`, `3677606`, `af05c4f`. Phase 4는 DB 마이그레이션 필요로 보류

## Past 2 [1774117636]
- **Task**: 스케줄 필터 확장 계획 수립 — 5가지 실제 문자 발송 시나리오 분석 및 필터 설계
- **Completed**: 현재 필터 로직 정리, 5가지 케이스 분석, 신규 필터/변수 6가지 설계, 프론트 UI 계획
- **Note**: 계획서 `.omc/plans/schedule-filter-expansion.md`, 사용자 검토 대기
