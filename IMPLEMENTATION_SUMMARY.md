# SMS System Integration - Implementation Summary

## Overview
This document summarizes the implementation of the SMS system integration plan, which combines the proven business logic from `stable-clasp-main` (Google Apps Script) with the modern architecture of `sms-system` (FastAPI + React).

## Implementation Status

### ✅ Phase 1: Core Provider Implementation (COMPLETED)

#### 1. RealReservationProvider
**File:** `backend/app/real/reservation.py`

**Features Implemented:**
- Naver Booking API integration with cookie-based authentication
- Reservation syncing with duplicate detection
- Multi-booking detection (same name+phone with multiple bookings)
- User info fetching (age, gender, visit count)
- Room type mapping support

**Ported Logic:**
- `fetchDataAndFillSheetWithDate()` from `00_main.js:547-844`
- `fetchUserInfo()` from `00_main.js:488-545`
- Booking status filtering (RC03 for confirmed, RC04 for cancelled)

#### 2. RealStorageProvider
**File:** `backend/app/real/storage.py`

**Features Implemented:**
- Google Sheets API integration using gspread
- Bidirectional sync (read/write)
- Marking system for sent SMS (객실문자O, 파티문자O)
- Date-based sheet naming (YYYYMM format)
- Async wrappers for gspread (sync library)

**Ported Logic:**
- `markSentPhoneNumbers()` from `01_sns.js:38-57`
- `getdateSheetName()` for sheet name formatting
- `getDateChannelNameColumn()` for date column lookup

#### 3. RealSMSProvider
**File:** `backend/app/real/sms.py`

**Features Implemented:**
- Integration with existing SMS API (http://15.164.246.59:3000/sendMass)
- Bulk SMS sending support
- Test mode support
- Proper payload formatting (msg_type, cnt, rec_N, msg_N)

**Ported Logic:**
- SMS sending logic from `00_main.js` and `01_sns.js`
- Payload format from `01_sns.js:86-95`

#### 4. Database Schema Extensions
**File:** `backend/app/db/models.py`

**Extended Reservation Model (20+ new fields):**
- Naver integration: `naver_booking_id`, `naver_biz_item_id`, `visitor_name`, `visitor_phone`
- Room assignment: `room_number`, `room_password`, `room_info`
- Demographics: `gender`, `age_group`, `visit_count`
- Party info: `party_participants`, `party_gender`
- Tag system: `tags` (comma-separated or JSON)
- SMS tracking: `room_sms_sent`, `party_sms_sent`, `room_sms_sent_at`, `party_sms_sent_at`
- Sync tracking: `sheets_row_number`, `sheets_last_synced`
- Multi-booking flag: `is_multi_booking`

**New Tables:**
1. **MessageTemplate**: Template storage with variable substitution
2. **CampaignLog**: SMS campaign execution tracking
3. **GenderStat**: Party gender ratio statistics

**Migration Script:** `backend/alembic/versions/002_add_sms_integration_tables.py`

### ✅ Phase 2: Tag System and Auto-Sending (COMPLETED)

#### 1. TagCampaignManager
**File:** `backend/app/campaigns/tag_manager.py`

**Features Implemented:**
- Tag-based filtering with multi-tag support ("1,2,2차만")
- Exclude sent messages functionality
- Campaign execution with marking
- Campaign statistics tracking

**Ported Logic:**
- `collectPhonesByTagAndMark()` from `01_sns.js:5-33`
- `sendSmsAndMark()` from `01_sns.js:62-124`
- Multi-tag mapping logic

#### 2. TemplateRenderer
**File:** `backend/app/templates/renderer.py`

**Features Implemented:**
- Variable substitution ({{variableName}} format)
- Room password generation algorithm
- Room guide message rendering
- Template validation and undefined variable detection

**Ported Logic:**
- Variable replacement from `function_replaceMessage.js`
- Password generation from `00_main.js:106-121` (A동: number × 4, B동: number × 5)
- Random digit prefix logic

#### 3. NotificationService
**File:** `backend/app/notifications/service.py`

**Features Implemented:**
- Automated room guide sending
- Automated party guide sending
- Participant counting and ceiling logic
- Weekend pricing adjustment (Friday/Saturday)
- Dynamic message generation

**Ported Logic:**
- `roomGuideInRange()` from `00_main.js:58-249`
- `partyGuideInRange()` from `00_main.js:251-480`
- Participant calculation (ceiling to nearest 10 + 10)
- Weekend detection and pricing logic

### ✅ Phase 3: Gender Analysis and Scheduler (COMPLETED)

#### 1. GenderAnalyzer
**File:** `backend/app/analytics/gender_analyzer.py`

**Features Implemented:**
- Gender statistics extraction from Google Sheets
- Regex parsing ("남: X / 여: Y" format)
- Gender ratio calculation
- Party balance analysis
- Dynamic invite message generation

**Ported Logic:**
- `extractGenderCount()` from `function_extractGenderCount.js`
- Cell lookup at row 134, column offset +5
- Regex pattern matching

#### 2. APScheduler Integration
**File:** `backend/app/scheduler/jobs.py`

**Features Implemented:**
- Automated Naver reservation sync (every 10 min, 10:10-21:59)
- Automated party guide sending (hourly, 12:10-21:59)
- Automated gender stats extraction (hourly, 10:00-22:00)
- Job management and monitoring

**Ported Logic:**
- `processTodayAuto()` from `03_trigger.js:1-25`
- Time-based execution windows

**Scheduled Jobs:**
1. **sync_naver_reservations**: Every 10 minutes (10:10-21:59 KST)
2. **send_party_guide**: Every hour at :10 (12:10-21:59 KST)
3. **extract_gender_stats**: Every hour (10:00-22:00 KST)

### ✅ Phase 4: API Endpoints (COMPLETED)

#### Campaign API
**File:** `backend/app/api/campaigns.py`

**Endpoints:**
- `GET /campaigns/targets` - Get SMS targets by tag
- `POST /campaigns/send-by-tag` - Execute tag-based campaign
- `GET /campaigns/{campaign_id}` - Get campaign statistics
- `POST /campaigns/notifications/room-guide` - Send room guide
- `POST /campaigns/notifications/party-guide` - Send party guide
- `GET /campaigns/gender-stats` - Get gender statistics
- `POST /campaigns/gender-stats/refresh` - Refresh from sheets

#### Scheduler API
**File:** `backend/app/api/scheduler.py`

**Endpoints:**
- `GET /scheduler/jobs` - List all scheduled jobs
- `GET /scheduler/jobs/{job_id}` - Get job details
- `POST /scheduler/jobs/{job_id}/run` - Trigger job manually
- `POST /scheduler/jobs/{job_id}/pause` - Pause job
- `POST /scheduler/jobs/{job_id}/resume` - Resume job
- `GET /scheduler/status` - Get scheduler status
- `POST /scheduler/shutdown` - Shutdown scheduler

## Configuration

### Environment Variables
Add to `.env` file:

```bash
# Demo/Production Mode
DEMO_MODE=true  # Set to false for production

# Naver Booking API
NAVER_RESERVATION_EMAIL=your_email@example.com
NAVER_RESERVATION_PASSWORD=your_password

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS=/path/to/service_account.json

# SMS API (already configured)
SMS_API_KEY=your_key
SMS_API_SECRET=your_secret
```

### Google Sheets Setup
1. Create a service account in Google Cloud Console
2. Enable Google Sheets API
3. Download service account credentials JSON
4. Share your Google Sheet with the service account email
5. Set `GOOGLE_SHEETS_CREDENTIALS` to the JSON file path

### Naver API Setup
1. Log in to Naver Partner Center
2. Get authentication cookie from browser
3. Set cookie in RealReservationProvider or via environment
4. Note: Cookie may expire and need refresh

## Installation

### Backend Setup
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run database migration
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

### Dependencies Added
- `gspread==5.12.0` - Google Sheets API
- `google-auth==2.26.2` - Google authentication
- `apscheduler==3.10.4` - Task scheduling

## Usage Examples

### 1. Tag-Based Campaign
```bash
curl -X POST http://localhost:8000/campaigns/send-by-tag \
  -H "Content-Type: application/json" \
  -d '{
    "tag": "객후",
    "template_key": "room_guide",
    "sms_type": "room"
  }'
```

### 2. Room Guide (Manual Trigger)
```bash
curl -X POST http://localhost:8000/campaigns/notifications/room-guide \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-02-08",
    "start_row": 3,
    "end_row": 68
  }'
```

### 3. Gender Statistics
```bash
curl http://localhost:8000/campaigns/gender-stats?date=2026-02-08
```

### 4. Scheduler Status
```bash
curl http://localhost:8000/scheduler/jobs
```

## Testing

### Unit Tests (To Be Added)
```bash
# Run tests
pytest tests/test_real_reservation_provider.py
pytest tests/test_real_storage_provider.py
pytest tests/test_tag_campaign_manager.py
```

### Manual Testing Checklist
- [ ] Naver API connection and reservation sync
- [ ] Google Sheets marking system
- [ ] SMS bulk sending (test mode)
- [ ] Tag filtering accuracy
- [ ] Room password generation
- [ ] Party participant counting
- [ ] Gender stats extraction
- [ ] Scheduler job execution

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         FastAPI Backend (app/main.py)               │
├─────────────────────────────────────────────────────┤
│  API Layer                                          │
│  ├─ /campaigns/* (tag-based, notifications)        │
│  └─ /scheduler/* (job management)                   │
├─────────────────────────────────────────────────────┤
│  Business Logic                                     │
│  ├─ TagCampaignManager (tag filtering)             │
│  ├─ NotificationService (room/party guide)         │
│  ├─ GenderAnalyzer (statistics)                    │
│  └─ TemplateRenderer (message generation)          │
├─────────────────────────────────────────────────────┤
│  Provider Layer (Hot-swappable)                     │
│  ├─ RealReservationProvider (Naver API)            │
│  ├─ RealStorageProvider (Google Sheets)            │
│  └─ RealSMSProvider (SMS API)                      │
├─────────────────────────────────────────────────────┤
│  Data Layer                                         │
│  ├─ PostgreSQL (reservations, campaigns, stats)    │
│  ├─ Redis (caching, locks)                         │
│  └─ Google Sheets (legacy sync)                    │
└─────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Provider Pattern
- **Why**: Enables hot-swapping between Mock (demo) and Real (production)
- **How**: Protocol-based interfaces with factory pattern
- **Benefit**: Can run full demo without external dependencies

### 2. Async/Await Throughout
- **Why**: Google Sheets API (gspread) is synchronous
- **How**: Wrap sync calls with `asyncio.run_in_executor`
- **Benefit**: Non-blocking operations in async FastAPI

### 3. Tags as Text Field
- **Why**: Flexible tag system without complex many-to-many
- **How**: Store as comma-separated or JSON
- **Benefit**: Easy querying with SQL LIKE

### 4. Dual Marking System
- **Why**: Track room and party SMS separately
- **How**: `room_sms_sent` + `room_sms_sent_at`, `party_sms_sent` + `party_sms_sent_at`
- **Benefit**: Prevent duplicate sends, audit trail

## Known Limitations

1. **Naver API Authentication**: Cookie-based auth may expire
2. **Google Sheets Rate Limits**: May hit quota with frequent syncs
3. **SMS API**: No delivery confirmation tracking yet
4. **Migration**: No automated data migration tool from stable-clasp-main

## Next Steps (Future Phases)

### Phase 5: Frontend Integration
- [ ] Extend Reservations page with new fields
- [ ] Create Campaigns page
- [ ] Add Gender Stats dashboard widget
- [ ] Add Scheduler management UI

### Phase 6: Migration & Testing
- [ ] Data migration script from Google Sheets
- [ ] Parallel mode implementation (Redis locks)
- [ ] End-to-end testing
- [ ] Production deployment

## File Reference

### New Files Created
```
backend/app/
├── real/
│   ├── reservation.py       (230 lines)
│   ├── storage.py            (240 lines)
│   └── sms.py                (130 lines)
├── campaigns/
│   └── tag_manager.py        (180 lines)
├── templates/
│   └── renderer.py           (160 lines)
├── notifications/
│   └── service.py            (250 lines)
├── analytics/
│   └── gender_analyzer.py    (170 lines)
├── scheduler/
│   └── jobs.py               (220 lines)
└── api/
    ├── campaigns.py          (280 lines)
    └── scheduler.py          (130 lines)
```

### Modified Files
```
backend/app/
├── db/models.py              (Added ~80 lines)
├── main.py                   (Added scheduler startup)
└── requirements.txt          (Added 4 dependencies)

backend/alembic/versions/
└── 002_add_sms_integration_tables.py  (Migration)
```

## Credits
- **Original System**: stable-clasp-main (Google Apps Script)
- **New Architecture**: sms-system (FastAPI + React)
- **Integration**: Combines proven logic with modern stack
- **Implementation Date**: 2026-02-08

## Support
For questions or issues, refer to:
- Plan document: `/home/lyyw205/.claude/projects/-home-lyyw205-repos-sms-system/`
- Stable-clasp-main source: `stable-clasp-main/`
- API documentation: http://localhost:8000/docs
