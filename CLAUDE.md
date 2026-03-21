# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SMS Reservation System - 숙소(게스트하우스) 예약 관리 + SMS 자동 발송 시스템. 네이버 예약 연동, 객실 배정, 템플릿 기반 SMS 스케줄링, 파티 체크인 등을 지원합니다.

**핵심 아키텍처 패턴**:
1. **Provider Factory + Hot-Swap**: `DEMO_MODE` 환경변수로 Mock/Real 구현체 즉시 전환
2. **Multi-Tenant Isolation**: ContextVar 기반 테넌트 격리 (SELECT/INSERT 자동 필터링)
3. **Template Schedule System**: APScheduler + DB 기반 SMS 자동 발송 스케줄링

## Development Commands

### Backend Setup and Execution

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database with seed data
# Important: Delete old DB file if schema has changed
rm -f sms.db
python -m app.db.seed

# Run development server
uvicorn app.main:app --reload

# Run on custom port
uvicorn app.main:app --reload --port 8001
```

**API Documentation**: http://localhost:8000/docs (Swagger UI automatically generated)

### Frontend Setup and Execution

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (if not already installed)
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

**Frontend URL**: http://localhost:5173 (or auto-incremented port if in use)

### Docker Services

```bash
# Start all services (PostgreSQL, Redis, ChromaDB)
docker compose up -d

# Start specific service
docker compose up -d postgres

# Stop all services
docker compose down

# View logs
docker compose logs -f
```

**Note**: Docker is optional for development. The backend can run with SQLite instead.

### Database Management

```bash
# Reseed database (wipes and recreates all tables + sample data)
cd backend
rm -f sms.db  # Delete old DB file first if schema changed
python -m app.db.seed

# Database migrations (Alembic)
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

## Architecture

### Multi-Tenant System

ContextVar 기반 자동 테넌트 격리 (`app/db/tenant_context.py`):
- **before_compile event**: 모든 SELECT에 `WHERE tenant_id = X` 자동 추가
- **before_flush event**: 모든 INSERT에 `tenant_id` 자동 주입
- **bypass_tenant_filter**: 스케줄러/마이그레이션 등 전역 작업 시 필터 우회
- **X-Tenant-Id 헤더**: 프론트엔드 요청마다 테넌트 지정 (`app/api/deps.py`)

### Provider Factory (Hot-Swap)

`app/factory.py` — 테넌트별 provider 생성:
- `get_sms_provider_for_tenant(tenant)`: Mock 또는 Real(Aligo API)
- `get_reservation_provider_for_tenant(tenant)`: Mock 또는 Real(네이버 API)
- `get_llm_provider()`: Mock(키워드 매칭) 또는 Real(Claude API, 미구현)

### SMS Template Schedule Pipeline

핵심 비즈니스 로직 — 예약 기반 자동 SMS 발송:
1. `TemplateSchedule` (DB) → APScheduler 등록 (`scheduler/schedule_manager.py`)
2. 트리거 시점 → `TemplateScheduleExecutor.execute_schedule()` (`scheduler/template_scheduler.py`)
3. 대상 예약 필터링 (building/room/assignment/column_match 조건)
4. 템플릿 변수 계산 (`templates/variables.py`) → 렌더링 (`templates/renderer.py`)
5. SMS 발송 (`services/sms_sender.py`) → ActivityLog 기록

### Room Assignment System

`services/room_assignment.py`:
- `assign_room()`: 객실 배정 (SELECT FOR UPDATE로 중복 방지)
- `sync_sms_tags()`: 배정 변경 시 ReservationSmsAssignment 자동 동기화
- `scheduler/room_auto_assign.py`: 자동 배정 (도미토리 성별 잠금, 용량 체크)

### Auto-Response Pipeline

`router/message_router.py`: DB Rules → YAML Rules → LLM → Review Queue
- confidence ≥ 0.6: 자동 발송
- confidence < 0.6: 사람 검토 대기열

## Key File Locations

### Configuration & Core
- `backend/app/config.py`: Pydantic Settings (`DEMO_MODE`, DB, API keys, JWT)
- `backend/app/factory.py`: 테넌트별 Provider Factory
- `backend/app/main.py`: FastAPI app (CORS, rate limit, 19개 라우터 등록, startup/shutdown)
- `backend/app/rate_limit.py`: slowapi + X-Forwarded-For 파싱

### Database Layer
- `backend/app/db/models.py`: 20+ SQLAlchemy 모델 (TenantMixin 적용)
- `backend/app/db/database.py`: 엔진/세션 + init_db() 자동 마이그레이션
- `backend/app/db/tenant_context.py`: ContextVar 기반 멀티테넌트 격리
- `backend/app/db/seed.py`: 초기 데이터 시딩 (admin/staff 계정)

### API Endpoints (19 routers)
- `auth.py`: 로그인, 토큰 갱신, 사용자 CRUD
- `reservations.py`: 예약 CRUD + 객실 배정/SMS 배정
- `reservations_sync.py`: 네이버 예약 동기화
- `rooms.py`: 객실 CRUD + N:M biz_item 매핑 + 캘린더
- `buildings.py`: 건물 CRUD
- `templates.py`: SMS 템플릿 CRUD + 변수 미리보기
- `template_schedules.py`: 스케줄 CRUD + APScheduler 연동
- `messages.py`: SMS 수발신 관리 + 연락처 목록
- `webhooks.py`: SMS 수신 웹훅 + 자동응답 파이프라인
- `auto_response.py`: 자동응답 테스트/생성
- `rules.py`: 자동응답 규칙 CRUD
- `dashboard.py`: 대시보드 통계 + 성별 예측
- `activity_logs.py`: 활동 로그 조회/통계
- `party_checkin.py`: 파티 체크인 토글
- `events.py`: SSE 실시간 이벤트
- `settings.py`: 테넌트 설정 (네이버 쿠키 등)
- `tenants.py`: 테넌트 목록
- `documents.py`: 지식 베이스 문서 관리
- `deps.py`: FastAPI 의존성 (테넌트 스코프 DB 세션)

### Services
- `services/sms_sender.py`: SMS 발송 (단건 + 배치) + ActivityLog
- `services/room_assignment.py`: 객실 배정 + SMS 태그 동기화
- `services/activity_logger.py`: 감사 로그 생성
- `services/event_bus.py`: SSE 브로드캐스트 (테넌트별 격리)
- `services/sms_tracking.py`: ReservationSmsAssignment 추적

### Scheduler
- `scheduler/jobs.py`: APScheduler 설정 + 네이버 동기화/상태 로그 작업
- `scheduler/template_scheduler.py`: 템플릿 스케줄 실행기 (필터링/발송)
- `scheduler/schedule_manager.py`: 스케줄 ↔ APScheduler 트리거 관리
- `scheduler/room_auto_assign.py`: 자동 객실 배정 (도미토리 성별 잠금)

### Templates
- `templates/renderer.py`: `{{변수}}` 치환 + 객실 비밀번호 생성
- `templates/variables.py`: 템플릿 변수 계산 (ParticipantSnapshot 캐시)

### Auth
- `auth/utils.py`: bcrypt 해싱 + JWT 생성/검증
- `auth/dependencies.py`: FastAPI 인증 의존성 (역할 기반 접근 제어)

### Providers
- `providers/base.py`: Protocol 정의 (SMSProvider, ReservationProvider, LLMProvider)
- `mock/sms.py`, `mock/llm.py`: 데모용 Mock 구현
- `real/sms.py`: Aligo SMS API (SMS/LMS 자동 감지, 500건 배치)
- `real/reservation.py`: 네이버 스마트플레이스 API (쿠키 인증, 성별/연령 조회)
- `real/llm.py`: Claude API (미구현 stub)

### Frontend
- `src/App.tsx`: React Router (역할별 라우트 보호)
- `src/pages/`: 12개 페이지 (Dashboard, Reservations, RoomAssignment, RoomSettings, Templates, Messages, AutoResponse, ActivityLogs, PartyCheckin, Settings, Login, UserManagement)
- `src/services/api.ts`: Axios 클라이언트 (자동 토큰 갱신, X-Tenant-Id 헤더)
- `src/stores/`: Zustand (auth-store, tenant-store)
- `src/components/Layout.tsx`: 사이드바 + 역할별 네비게이션

## Database Schema

### Core Models (all TenantMixin except User, Tenant)

| 모델 | 용도 | 핵심 필드 |
|------|------|-----------|
| `User` | 인증 | username, hashed_password, role (SUPERADMIN/ADMIN/STAFF) |
| `Tenant` | 멀티테넌트 | slug, name, naver_business_id, naver_cookie, aligo_sender |
| `Reservation` | 예약 | customer_name, phone, check_in/out_date, section (room/party/unassigned), male_count, female_count |
| `Message` | SMS 이력 | direction, from_, to, content, auto_response, confidence, needs_review, response_source |
| `Room` | 객실 | room_number, room_type, is_dormitory, base/max_capacity, building_id |
| `Building` | 건물 | name, sort_order, is_active |
| `RoomAssignment` | 일자별 배정 | reservation_id, date, room_number, room_password, assigned_by |
| `RoomBizItemLink` | N:M 매핑 | room_id, biz_item_id, male/female_priority |
| `NaverBizItem` | 네이버 상품 | biz_item_id, name, is_exposed |
| `MessageTemplate` | SMS 템플릿 | template_key, content, variables (JSON), category, participant_buffer |
| `TemplateSchedule` | 발송 스케줄 | template_id, schedule_type, hour, minute, filters (JSON), target_mode |
| `ReservationSmsAssignment` | SMS 추적 | reservation_id, template_key, date, assigned_by, sent_at |
| `Rule` | 자동응답 규칙 | pattern (regex), response, priority, is_active |
| `ActivityLog` | 감사 로그 | activity_type, title, detail (JSON), target/success/failed_count |
| `PartyCheckin` | 파티 출석 | reservation_id, date, checked_in_at |
| `ReservationDailyInfo` | 일자별 오버라이드 | reservation_id, date, party_type |
| `ParticipantSnapshot` | 성별 캐시 | date, male_count, female_count |
| `GenderStat` | 인구통계 | date, male_count, female_count |

### Enums
- `UserRole`: SUPERADMIN, ADMIN, STAFF
- `MessageDirection`: INBOUND, OUTBOUND
- `MessageStatus`: PENDING, SENT, FAILED, RECEIVED
- `ReservationStatus`: PENDING, CONFIRMED, CANCELLED, COMPLETED

## Environment Variables

`backend/.env` 주요 설정:

- `DEMO_MODE`: `true` (mock) / `false` (production) — **핵심 스위치**
- `DATABASE_URL`: `sqlite:///./sms.db` (데모) / `postgresql://...` (운영)
- `JWT_SECRET_KEY`: 데모 모드에서 자동 생성
- `ADMIN_DEFAULT_PASSWORD`, `STAFF_DEFAULT_PASSWORD`: 데모 모드에서 자동 생성

운영 전용 (`DEMO_MODE=false`):
- `ALIGO_API_KEY`, `ALIGO_USER_ID`, `ALIGO_SENDER`: Aligo SMS API
- `CLAUDE_API_KEY`: Anthropic Claude API
- 네이버 쿠키: DB Tenant 레코드에 저장 (런타임 업데이트 가능)

## Scheduler Jobs

| Job | 주기 | 설명 |
|-----|------|------|
| `sync_naver_reservations_job` | 5분 | 네이버 예약 동기화 (전 테넌트) |
| `sync_status_log_job` | 6시간 (00,06,12,18) | 동기화 상태 로그 기록 |
| `daily_room_assign_job` | 매일 | 미래 날짜 자동 객실 배정 |
| `TemplateSchedule` 기반 | DB 설정 | 템플릿별 SMS 자동 발송 |

## Common Development Patterns

### API 엔드포인트 추가
1. `app/api/[domain].py`에 라우터 작성
2. `get_tenant_scoped_db()` 의존성으로 테넌트 격리 DB 세션 획득
3. `app/main.py`에 라우터 등록

### SMS 템플릿 변수
`{{customer_name}}`, `{{room_num}}`, `{{building}}`, `{{room_password}}`, `{{participant_count}}`, `{{male_count}}`, `{{female_count}}` 등 — `templates/variables.py`의 `calculate_template_variables()` 참조

### ActivityLog 기록
```python
from app.services.activity_logger import log_activity
log_activity(db, type="sms_send", title="...", detail={...},
             target_count=1, success_count=1, created_by="system")
```

## Frontend Design Guidelines

프론트엔드는 **Toss Invest 디자인 시스템** 기반 + **Flowbite React** 컴포넌트 라이브러리를 사용합니다. 새 페이지나 컴포넌트 작성 시 아래 규칙을 반드시 따르세요.

### 핵심 파일
- `frontend/src/index.css`: 디자인 토큰 (타이포그래피, 색상, 컴포넌트 클래스)
- `frontend/src/components/FlowbiteTheme.tsx`: Flowbite 커스텀 테마 오버라이드

### 색상 팔레트 (Toss-inspired)

| 토큰 | 값 | 용도 |
|------|------|------|
| Primary Blue | `#3182F6` | 주요 액션, 활성 상태, 링크 |
| Blue Light | `#E8F3FF` | Blue 배경 (뱃지, 활성 사이드바) |
| Success | `#00C9A7` | 확정, 성공, 완료 |
| Warning | `#FF9F00` | 대기, 주의 |
| Error | `#F04452` | 취소, 삭제, 에러 |
| Text Primary | `#191F28` | 제목, 본문 (dark: `white`) |
| Text Secondary | `#4E5968` | 보조 텍스트 (dark: `gray-300`) |
| Text Tertiary | `#8B95A1` | 라벨, 비활성 (dark: `gray-500`) |
| Text Disabled | `#B0B8C1` | 플레이스홀더, 비활성 (dark: `gray-600`) |
| Border | `#E5E8EB` | 입력 필드 테두리, 구분선 |
| Background | `#F2F4F6` | 카드 배경, 호버 (dark: `#2C2C34`) |
| Surface | `#F8F9FA` | stat-card 배경 (dark: `#1E1E24`) |

### 타이포그래피 (CSS 커스텀 클래스)

| 클래스 | 크기 | 행간 | 굵기 | 용도 |
|--------|------|------|------|------|
| `text-display` | 28px | 36px | bold | Hero, 대시보드 대형 숫자 |
| `text-title` | 22px | 30px | bold | 페이지 제목 (`.page-title`) |
| `text-heading` | 18px | 26px | semibold | 섹션 제목, 모달 제목 |
| `text-subheading` | 15px | 22px | semibold | 카드 제목, 네비 브랜드 |
| `text-body` | 14px | 20px | regular | **본문 기본값** |
| `text-label` | 13px | 18px | medium | 서브타이틀, 보조 본문 |
| `text-caption` | 12px | 16px | medium | 테이블 헤더, 캡션, 도움말 |
| `text-overline` | 11px | 16px | semibold | 카테고리 라벨 |
| `text-tiny` | 10px | 14px | regular | 타임스탬프, 뱃지 |

### 버튼 규칙 (Flowbite `<Button>`)

| 위치 | `size` | `color` | 아이콘 크기 | 예시 |
|------|--------|---------|-------------|------|
| 페이지 헤더 액션 | `sm` | `blue` 또는 `light` | `h-3.5 w-3.5` | 예약 등록, 네이버 동기화, 객실안내 |
| 테이블 인라인 액션 | `xs` | `light` 또는 `failure` | `h-3.5 w-3.5` | 수정, 삭제 버튼 |
| 모달 푸터 | (기본) | `blue` + `light` | — | 저장/취소 |
| 삭제 확인 모달 | (기본) | `failure` + `light` | — | 삭제/취소 |

**규칙:**
- 버튼 내 아이콘은 `mr-1.5` 간격으로 텍스트 앞에 배치
- 아이콘 전용 버튼(테이블 내)은 `mr` 없이 아이콘만
- 로딩 시 `<Spinner size="sm" className="mr-2" />` + "저장 중..." 텍스트

### 아이콘 (Lucide React)

| 컨텍스트 | 크기 | 비고 |
|----------|------|------|
| 버튼 내부 (sm/xs) | `h-3.5 w-3.5` | 가장 많이 사용 |
| 독립 아이콘 (필터 등) | `h-4 w-4` | 검색, 닫기, 네비게이션 |
| stat-card 아이콘 | `size={18}` (lucide prop) | `.stat-icon` 컨테이너 안 |
| 빈 상태 일러스트 | `size={40}` 또는 `h-10 w-10` | `.empty-state` 안 |

### 간격 (Gap) 규칙

| 컨텍스트 | gap | 비고 |
|----------|-----|------|
| 페이지 헤더 ↔ 콘텐츠 | `space-y-6` | 최상위 레이아웃 |
| 버튼 그룹 (헤더) | `gap-2` | 수평 버튼 나열 |
| 테이블 인라인 버튼 | `gap-1` | 수정/삭제 버튼 쌍 |
| stat-card 그리드 | `gap-3` | `grid-cols-2 sm:3 lg:5` |
| 폼 필드 간격 | `gap-4` | 모달 내 수직 폼 |
| 필터 바 항목 | `gap-3` | `.filter-bar` 내부 |
| 카드 내부 요소 | `gap-3` | stat-icon ↔ 텍스트 |

### Badge 규칙 (Flowbite `<Badge>`)

| 용도 | `size` | `color` |
|------|--------|---------|
| 상태 표시 (확정/대기/취소) | `sm` | `success` / `warning` / `failure` |
| 출처 라벨 (네이버/수동) | `xs` | `success` / `gray` |
| 정보 표시 (객실, 태그) | `sm` | `info` / `purple` / `gray` |

### 모달 (Flowbite `<Modal>`)

| 용도 | `size` | 비고 |
|------|--------|------|
| 일반 폼 (생성/수정) | `md` | 대부분의 CRUD 모달 |
| 복잡한 폼 | `lg` | 여러 섹션이 있는 폼 |
| 삭제 확인 | `md` + `popup` | 아이콘 + 텍스트 + 버튼 중앙 정렬 |

### 컴포넌트 클래스 (index.css)

| 클래스 | 용도 |
|--------|------|
| `.page-title` | 페이지 제목 (`text-title font-bold`) |
| `.page-subtitle` | 페이지 설명 (`text-label text-[#8B95A1]`) |
| `.stat-card` | 통계 카드 컨테이너 (`rounded-2xl bg-[#F8F9FA] p-5`) |
| `.stat-value` | 통계 숫자 (`text-title font-bold tabular-nums`) |
| `.stat-label` | 통계 라벨 (`text-caption text-[#8B95A1]`) |
| `.stat-icon` | 통계 아이콘 래퍼 (`h-10 w-10 rounded-xl`) |
| `.section-card` | 섹션 카드 (`rounded-2xl border bg-white`) |
| `.section-header` | 섹션 헤더 (`px-5 py-4 flex justify-between`) |
| `.filter-bar` | 필터 바 (`flex flex-wrap gap-3 p-4`) |
| `.empty-state` | 빈 상태 (`flex flex-col items-center py-16`) |
| `.guest-card` | 게스트 드래그 카드 (`cursor-grab rounded-xl`) |
| `.room-cell` | 객실 드롭 영역 (`border-2 border-dashed`) |

### 다크 모드 패턴

- 배경: `dark:bg-[#17171C]` (body), `dark:bg-[#1E1E24]` (카드/셀)
- 호버: `dark:hover:bg-[#2C2C34]` 또는 `dark:hover:bg-[#35353E]`
- 테두리: `dark:border-gray-800` (기본), `dark:border-gray-600` (입력 필드)
- 텍스트: `dark:text-white` (제목), `dark:text-gray-100` (본문), `dark:text-gray-500` (보조)
- 뱃지/칩 배경: `dark:bg-[색상]/15` 패턴 (예: `dark:bg-[#3182F6]/15`)

### 페이지 레이아웃 패턴

```
<div className="space-y-6">
  {/* 헤더: 제목 + 액션 버튼 */}
  <div className="flex flex-wrap items-start justify-between gap-4">
    <div>
      <h1 className="page-title">페이지 제목</h1>
      <p className="page-subtitle">설명 텍스트</p>
    </div>
    <div className="flex items-center gap-2">
      <Button color="light" size="sm">...</Button>
      <Button color="blue" size="sm">...</Button>
    </div>
  </div>

  {/* stat-card 그리드 (선택) */}
  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
    <div className="stat-card">...</div>
  </div>

  {/* 메인 콘텐츠 */}
  <div className="section-card">...</div>
</div>
```

### 숫자 표시
- 숫자에는 `tabular-nums` 클래스 적용 (고정폭 숫자)
- 단위는 `<span className="ml-0.5 text-label font-normal text-[#B0B8C1]">건</span>` 형태

### 반올림(Border Radius) 규칙
- 카드, 모달: `rounded-2xl` (16px)
- 버튼, 뱃지, 입력: `rounded-lg` (8px)
- stat-icon: `rounded-xl` (12px)
- 채팅 버블: `rounded-[20px]` + 꼬리 `rounded-bl-[4px]`

## Notes

- SQLAlchemy ORM: SQLite (데모) + PostgreSQL (운영) 지원
- 타임존: Asia/Seoul (KST) 사용
- 프론트엔드: Flowbite React + Toss Invest 디자인 시스템 (NOT Ant Design)
- UI/샘플 데이터: 한국어
- 인증: JWT (access 1h + refresh 7d), bcrypt 해싱
- 역할: SUPERADMIN → ADMIN → STAFF (파티 체크인만 접근 가능)
- 실시간: SSE 이벤트 버스 (`services/event_bus.py`)
- Aligo SMS: SMS(≤90바이트)/LMS(>90바이트) 자동 감지, 500건 배치
- 네이버 API: 쿠키 기반 인증, Semaphore(10) 동시성 제한
- CampaignLog: 레거시 (읽기 전용), 신규 활동은 ActivityLog 사용
- `_future/` 디렉토리: 미래 구현 예정 모듈
