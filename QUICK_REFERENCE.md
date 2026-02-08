# SMS Integration - Quick Reference Card

## 🚀 Startup Commands

```bash
# 1. Install dependencies
cd backend && pip install -r requirements.txt

# 2. Run database migration
alembic upgrade head

# 3. Start server
uvicorn app.main:app --reload

# 4. Access API docs
open http://localhost:8000/docs
```

## ⚙️ Configuration (.env)

```bash
# Demo mode (no credentials needed)
DEMO_MODE=true

# Production mode (requires credentials)
DEMO_MODE=false
NAVER_RESERVATION_EMAIL=email@example.com
NAVER_RESERVATION_PASSWORD=password
GOOGLE_SHEETS_CREDENTIALS=/path/to/credentials.json
```

## 📋 API Endpoints Summary

### Campaigns
```bash
# Get targets by tag
GET /campaigns/targets?tag=객후

# Send campaign
POST /campaigns/send-by-tag
{
  "tag": "객후",
  "template_key": "room_guide"
}

# Room guide
POST /campaigns/notifications/room-guide
{"date": "2026-02-08"}

# Party guide
POST /campaigns/notifications/party-guide
{"date": "2026-02-08"}

# Gender stats
GET /campaigns/gender-stats?date=2026-02-08
```

### Scheduler
```bash
# List jobs
GET /scheduler/jobs

# Trigger manually
POST /scheduler/jobs/sync_naver_reservations/run

# Pause/Resume
POST /scheduler/jobs/{id}/pause
POST /scheduler/jobs/{id}/resume

# Status
GET /scheduler/status
```

## 🗂️ Database Tables

```sql
-- Extended
reservations (20+ new fields)

-- New
message_templates
campaign_logs
gender_stats
```

## 🔧 Key Classes

```python
# Providers
RealReservationProvider  # Naver API
RealStorageProvider      # Google Sheets
RealSMSProvider          # SMS API

# Business Logic
TagCampaignManager       # Tag filtering
TemplateRenderer         # Message generation
NotificationService      # Auto-sending
GenderAnalyzer          # Statistics

# Scheduler
scheduler.jobs          # 3 automated jobs
```

## ⏰ Scheduled Jobs

```
sync_naver_reservations
├── Schedule: Every 10 min, 10:10-21:59 KST
└── Function: Sync from Naver API

send_party_guide
├── Schedule: Every hour at :10, 12:10-21:59 KST
└── Function: Send party guide to unassigned

extract_gender_stats
├── Schedule: Every hour, 10:00-22:00 KST
└── Function: Extract gender ratio from sheets
```

## 🧪 Quick Tests

```bash
# Test 1: Scheduler status
curl http://localhost:8000/scheduler/jobs | jq

# Test 2: Tag filtering
curl "http://localhost:8000/campaigns/targets?tag=test" | jq

# Test 3: Manual sync trigger
curl -X POST http://localhost:8000/scheduler/jobs/sync_naver_reservations/run

# Test 4: Gender stats
curl "http://localhost:8000/campaigns/gender-stats" | jq
```

## 🐛 Troubleshooting

**Server won't start:**
```bash
# Check database
psql -U smsuser -d smsdb

# Check dependencies
pip list | grep -E "(gspread|apscheduler|fastapi)"
```

**Scheduler not running:**
```bash
# Check logs
uvicorn app.main:app --reload --log-level debug

# Verify jobs
curl http://localhost:8000/scheduler/jobs
```

**Naver API fails:**
```bash
# Check DEMO_MODE
cat .env | grep DEMO_MODE

# In production, check cookie expiry
```

## 📁 Important Files

```
backend/app/
├── config.py           # DEMO_MODE flag
├── factory.py          # Provider factory
├── main.py             # App startup
├── db/models.py        # Database schema
│
├── real/               # Production providers
│   ├── reservation.py
│   ├── storage.py
│   └── sms.py
│
├── campaigns/          # Campaign management
│   └── tag_manager.py
│
├── templates/          # Message rendering
│   └── renderer.py
│
├── notifications/      # Auto-sending
│   └── service.py
│
├── analytics/          # Statistics
│   └── gender_analyzer.py
│
└── scheduler/          # Automation
    └── jobs.py
```

## 🎯 Common Tasks

### Send Room Guide
```bash
curl -X POST http://localhost:8000/campaigns/notifications/room-guide \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-02-08", "start_row": 3, "end_row": 68}'
```

### Execute Tag Campaign
```bash
curl -X POST http://localhost:8000/campaigns/send-by-tag \
  -H "Content-Type: application/json" \
  -d '{
    "tag": "객후",
    "template_key": "room_guide",
    "sms_type": "room"
  }'
```

### Check Campaign Results
```bash
# Get campaign by ID
curl http://localhost:8000/campaigns/campaigns/1 | jq

# Check database
psql -U smsuser -d smsdb -c \
  "SELECT * FROM campaign_logs ORDER BY id DESC LIMIT 5;"
```

### View Gender Stats
```bash
curl "http://localhost:8000/campaigns/gender-stats?date=2026-02-08" | jq
```

## 📊 Database Queries

```sql
-- Check extended reservation fields
SELECT naver_booking_id, room_number, tags,
       room_sms_sent, party_sms_sent
FROM reservations
LIMIT 5;

-- View campaign logs
SELECT id, campaign_type, target_count, sent_count, sent_at
FROM campaign_logs
ORDER BY id DESC
LIMIT 10;

-- View gender stats
SELECT date, male_count, female_count, total_participants
FROM gender_stats
ORDER BY date DESC;

-- Check message templates
SELECT key, name, category
FROM message_templates
WHERE active = true;
```

## 🔐 Environment Variables

```bash
# Core
DEMO_MODE=true/false
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379

# Naver (Production only)
NAVER_RESERVATION_EMAIL=
NAVER_RESERVATION_PASSWORD=

# Google (Production only)
GOOGLE_SHEETS_CREDENTIALS=

# SMS (Production only)
SMS_API_KEY=
SMS_API_SECRET=
```

## 📖 Documentation

- **Full Documentation:** IMPLEMENTATION_SUMMARY.md
- **Testing Guide:** TESTING_GUIDE.md
- **API Reference:** http://localhost:8000/docs
- **This Card:** QUICK_REFERENCE.md
