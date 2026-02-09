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

## Notes

- The system uses SQLAlchemy ORM with both SQLite (demo) and PostgreSQL (production) support
- All datetime fields use UTC (`datetime.utcnow`)
- Frontend uses Ant Design for UI components
- Korean language is used in UI and sample data
- The `app/router/message_router.py` implements the core auto-response intelligence
- ChromaDB is prepared for RAG but only used when `DEMO_MODE=false`
- The scheduler uses APScheduler for automated tasks (Naver sync, SMS campaigns, analytics)
