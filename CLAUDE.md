# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SMS Reservation System - A demo/MVP system for automating SMS responses and managing reservations. The system uses a **hot-swap architecture** that switches between Mock (demo) and Real (production) providers via a single environment variable (`DEMO_MODE`).

**Key Architectural Pattern**: Provider Factory Pattern with Protocol-based abstraction allows seamless switching between mock and production implementations without code changes.

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

### Hot-Swap Provider System

The system's core architectural pattern is the **Provider Factory** that enables instant switching between demo and production modes:

1. **Protocol Interfaces** (`app/providers/base.py`): Define abstract contracts for all external integrations
   - `SMSProvider`: SMS sending/receiving
   - `LLMProvider`: Claude API for auto-responses
   - `ReservationProvider`: Naver Booking sync
   - `StorageProvider`: Google Sheets integration

2. **Factory** (`app/factory.py`): Central decision point that returns Mock or Real implementations based on `settings.DEMO_MODE`
   ```python
   def get_sms_provider() -> SMSProvider:
       if settings.DEMO_MODE:
           return MockSMSProvider()
       else:
           return RealSMSProvider(api_key=settings.SMS_API_KEY)
   ```

3. **Mock Implementations** (`app/mock/`): Demo-safe versions that log to console and use local files
4. **Real Implementations** (`app/real/`): Production versions integrating actual external APIs (stubs ready for implementation)

### Message Processing Flow

**Auto-Response Pipeline**:
1. SMS arrives → `POST /webhooks/sms/receive` (or simulation via frontend)
2. Message saved to database with `status=received`, `direction=inbound`
3. `MessageRouter` (`app/router/message_router.py`) executes routing logic:
   - **Step 1**: Try `RuleEngine` (regex pattern matching from `app/rules/rules.yaml`, confidence: 0.95)
   - **Step 2**: If no rule matches, fallback to `LLMProvider` (Mock: keyword matching, Real: Claude API + RAG)
   - **Step 3**: Check confidence threshold (≥0.6 = auto-send, <0.6 = human review queue)
4. If auto-approved, `SMSProvider.send_sms()` is called
5. Outbound message saved with `direction=outbound`, `status=sent`

### Reservation Event System

SQLAlchemy event listeners trigger automatic SMS notifications when reservation status changes:

```python
# app/notifications/service.py
@event.listens_for(Reservation, "after_insert")
@event.listens_for(Reservation, "after_update")
def send_reservation_notification(mapper, connection, target):
    # Sends SMS based on status: pending, confirmed, cancelled, completed
```

## Key File Locations

### Configuration
- `backend/app/config.py`: Settings with `DEMO_MODE` flag (critical for hot-swap)
- `backend/.env`: Environment variables (copy from `.env.example`)
- `backend/app/factory.py`: Provider factory (hot-swap implementation)

### Backend API Layers
- `backend/app/api/`: FastAPI route handlers
  - `messages.py`: SMS message management
  - `reservations.py`: Reservation CRUD and sync
  - `rules.py`: Auto-response rule management
  - `documents.py`: Knowledge base document management
  - `campaigns.py`: Bulk SMS campaigns
  - `webhooks.py`: SMS receive webhook
  - `dashboard.py`: Dashboard statistics
  - `scheduler.py`: Scheduled jobs management
  - `auto_response.py`: Auto-response testing and rule reload

### Message Routing
- `backend/app/router/message_router.py`: Auto-response routing logic (Rule → LLM → Human)
- `backend/app/rules/engine.py`: Regex-based rule matching engine
- `backend/app/rules/rules.yaml`: Business rules for auto-responses

### Database
- `backend/app/db/models.py`: SQLAlchemy models (Message, Reservation, Rule, Document, etc.)
- `backend/app/db/database.py`: Database session management
- `backend/app/db/seed.py`: Sample data seeding script

### Provider Implementations
- `backend/app/providers/base.py`: Protocol definitions
- `backend/app/mock/`: Mock implementations (sms.py, llm.py, reservation.py, storage.py)
- `backend/app/real/`: Real implementations (stubs ready for production)

### Frontend Structure
- `frontend/src/App.tsx`: Main app with React Router setup
- `frontend/src/pages/`: Page components
  - `Dashboard.tsx`: Statistics and charts
  - `Messages.tsx`: SMS inbox with simulator
  - `Reservations.tsx`: Reservation management
  - `Rules.tsx`: Auto-response rule editor
  - `Documents.tsx`: Knowledge base uploader
  - `RoomAssignment.tsx`: Room assignment with password generation
  - `Campaigns.tsx`: Bulk SMS campaign manager
  - `Scheduler.tsx`: Scheduled job configuration
  - `AutoResponse.tsx`: Auto-response testing interface
- `frontend/src/components/`: Reusable components
- `frontend/src/services/`: API client using Axios
- `frontend/vite.config.ts`: Vite configuration with proxy setup

### Additional Modules
- `backend/app/notifications/`: SMS notification service with event listeners
- `backend/app/scheduler/`: APScheduler jobs for automated tasks
- `backend/app/campaigns/`: Bulk SMS campaign logic
- `backend/app/analytics/`: Gender and demographic analysis
- `backend/app/templates/`: SMS template rendering with Jinja2

## Database Schema

### Core Tables
- **messages**: SMS history with auto-response metadata
  - `auto_response`: Generated response text
  - `auto_response_confidence`: Confidence score (0-1)
  - `needs_review`: Human review flag
  - `response_source`: 'rule', 'llm', or 'manual'

- **reservations**: Extended schema with Naver Booking integration
  - `naver_booking_id`: Naver Booking ID
  - `room_number`, `room_password`: Room assignment
  - `gender`, `age_group`: Demographics
  - `tags`: Comma-separated tags (e.g., "객후,1초,2차만")
  - `room_sms_sent`, `party_sms_sent`: SMS tracking flags

- **rules**: Auto-response rules
  - `pattern`: Regex pattern for matching
  - `response`: Response template (supports Jinja2)
  - `priority`: Higher priority rules matched first
  - `active`: Enable/disable flag

- **documents**: Knowledge base for RAG
  - `content`: Document text
  - `indexed`: ChromaDB indexing status

- **message_templates**: Reusable SMS templates
- **campaign_logs**: Bulk SMS campaign history
- **gender_stats**: Demographics analysis results

## Environment Variables

Critical settings in `backend/.env`:

- `DEMO_MODE`: `true` (mock) or `false` (production) - **THE hot-swap switch**
- `DATABASE_URL`: Database connection string
  - Demo: `sqlite:///./sms.db`
  - Production: `postgresql://smsuser:smspass@localhost:5432/smsdb`
- `REDIS_URL`: Redis connection for caching/queues (optional in demo mode)
- `CHROMADB_URL`: Vector database for RAG (optional in demo mode)

Production-only (required when `DEMO_MODE=false`):
- `SMS_API_KEY`, `SMS_API_SECRET`: NHN Cloud SMS API
- `CLAUDE_API_KEY`: Anthropic Claude API
- `GOOGLE_SHEETS_CREDENTIALS`: Service account JSON path
- `NAVER_RESERVATION_EMAIL`, `NAVER_RESERVATION_PASSWORD`: Naver Booking credentials

## Demo Mode vs Production Mode

**Current State**: System runs in `DEMO_MODE=true` by default

### Demo Mode (`DEMO_MODE=true`)
- All external API calls are mocked
- SMS sends print to console with `[MOCK SMS SENT]` logs
- LLM uses keyword matching instead of Claude API
- Naver sync reads from `backend/app/mock/data/naver_reservations.json`
- Google Sheets writes to `backend/app/mock/data/reservations.csv`
- Zero external costs, safe for demos

### Production Mode (`DEMO_MODE=false`)
- Real API integrations activate
- Requires all API keys in `.env`
- Real implementations in `app/real/` are used
- Estimated transition time: 9 hours (implement Real providers + integration testing)

## Testing & Debugging

### API Testing
Use Swagger UI at http://localhost:8000/docs to test all endpoints interactively.

### SMS Simulation (Demo Mode)
Frontend includes SMS Simulator component on Messages page:
1. Enter phone number and message
2. Click "수신 시뮬레이션"
3. Check terminal logs for `[MOCK SMS RECEIVED]` and `[MOCK SMS SENT]`
4. Message appears in database and frontend table

### Rule Testing
```bash
# Test auto-response without saving to DB
POST /api/auto-response/test
Body: {"message": "영업시간이 어떻게 되나요?"}
```

### Hot-Reload Rules
```bash
# Reload rules.yaml without restarting server
POST /api/auto-response/reload-rules
```

### Background Tasks
The scheduler runs automated tasks:
- Naver reservation sync (configurable interval)
- Party guide SMS sending (scheduled time)
- Gender statistics extraction (daily)

## Common Development Patterns

### Adding a New Provider Type

1. Define Protocol in `app/providers/base.py`:
   ```python
   class NewProvider(Protocol):
       async def some_method(self, param: str) -> Dict[str, Any]: ...
   ```

2. Create Mock in `app/mock/new_provider.py`:
   ```python
   class MockNewProvider:
       async def some_method(self, param: str) -> Dict[str, Any]:
           logger.info(f"[MOCK NEW PROVIDER] Called with {param}")
           return {"result": "mocked"}
   ```

3. Create Real stub in `app/real/new_provider.py`

4. Add factory function in `app/factory.py`:
   ```python
   def get_new_provider() -> NewProvider:
       if settings.DEMO_MODE:
           return MockNewProvider()
       else:
           return RealNewProvider()
   ```

### Adding Auto-Response Rules

Edit `backend/app/rules/rules.yaml`:
```yaml
- name: "New Rule"
  pattern: "keyword|phrase"  # Regex pattern
  response: "Response template with {customer_name}"
  priority: 10
  active: true
```

Reload without restart: `POST /api/auto-response/reload-rules`

### Adding API Endpoints

1. Create handler in `app/api/[domain].py`
2. Use factory functions to get providers: `sms_provider = get_sms_provider()`
3. Register router in `app/main.py`

## Common Issues and Solutions

### Port Already in Use
```bash
# Find process using port
lsof -i :8000  # or netstat -tlnp | grep 8000

# Kill process
kill <PID>

# Or use different port
uvicorn app.main:app --reload --port 8001
```

### Database Schema Mismatch
```bash
# Delete old database and reseed
cd backend
rm -f sms.db
python -m app.db.seed
```

### Dependency Version Conflicts
If `anthropic` version conflicts occur, the package should be `>=0.16.0` to satisfy `langchain-anthropic` requirements.

### Frontend Proxy Issues
The frontend uses Vite proxy to avoid CORS issues. Proxy configuration in `frontend/vite.config.ts`:
```typescript
proxy: {
  '/api': { target: 'http://localhost:8000' },
  '/webhooks': { target: 'http://localhost:8000' }
}
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

- The system uses SQLAlchemy ORM with both SQLite (demo) and PostgreSQL (production) support
- All datetime fields use UTC (`datetime.utcnow`)
- Frontend uses Flowbite React + Toss Invest design system (NOT Ant Design)
- Korean language is used in UI and sample data
- The `app/router/message_router.py` implements the core auto-response intelligence
- ChromaDB is prepared for RAG but only used when `DEMO_MODE=false`
- The scheduler uses APScheduler for automated tasks (Naver sync, SMS campaigns, analytics)
