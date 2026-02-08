# SMS System Integration - Testing Guide

## Pre-Testing Setup

### 1. Environment Configuration
Create `.env` file in `backend/` directory:

```bash
# Mode Selection
DEMO_MODE=true  # Start with demo mode for testing

# Database
DATABASE_URL=postgresql://smsuser:smspass@localhost:5432/smsdb

# Redis
REDIS_URL=redis://localhost:6379

# ChromaDB
CHROMADB_URL=http://localhost:8001

# For Production Testing (DEMO_MODE=false)
NAVER_RESERVATION_EMAIL=your_email@example.com
NAVER_RESERVATION_PASSWORD=your_password
GOOGLE_SHEETS_CREDENTIALS=/path/to/service_account.json
SMS_API_KEY=your_key
SMS_API_SECRET=your_secret
```

### 2. Database Setup
```bash
cd backend

# Run migrations
alembic upgrade head

# Verify tables created
psql -U smsuser -d smsdb -c "\dt"
# Should show: reservations, message_templates, campaign_logs, gender_stats
```

### 3. Start Server
```bash
uvicorn app.main:app --reload
```

Verify startup logs show:
```
✓ Database initialized
✓ Scheduler started
✓ MockReservationProvider (or RealReservationProvider if DEMO_MODE=false)
```

## Testing Checklist

### Phase 1: Core Providers

#### Test 1.1: RealReservationProvider (Demo Mode)
```bash
# Start in demo mode (DEMO_MODE=true)
# The mock provider will return sample data

curl http://localhost:8000/api/reservations
```

**Expected Result:**
- Returns mock reservations with proper structure
- Fields include: id, customer_name, phone, date, time, status

#### Test 1.2: Database Models
```bash
# Check extended reservation fields
psql -U smsuser -d smsdb

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'reservations';
```

**Expected Fields:**
- naver_booking_id
- room_number, room_password
- gender, age_group
- tags
- room_sms_sent, party_sms_sent
- And all other new fields

#### Test 1.3: SMS Provider (Test Mode)
```bash
curl -X POST http://localhost:8000/api/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "to": "01012345678",
    "message": "Test message"
  }'
```

**Expected Result (Demo Mode):**
```json
{
  "message_id": "mock_msg_xxx",
  "status": "sent",
  "timestamp": "2026-02-08T..."
}
```

### Phase 2: Tag System & Templates

#### Test 2.1: Create Message Template
```bash
curl -X POST http://localhost:8000/api/templates \
  -H "Content-Type: application/json" \
  -d '{
    "key": "test_template",
    "name": "Test Template",
    "content": "Hello {{name}}, your room is {{roomNumber}}",
    "variables": ["name", "roomNumber"],
    "category": "test"
  }'
```

#### Test 2.2: Room Password Generation
```python
# Python test
from app.templates.renderer import TemplateRenderer

# Test A building
password_a = TemplateRenderer.generate_room_password("A101")
print(f"A101 password: {password_a}")  # Should be like "50404" (random digit + 0 + 404)

# Test B building
password_b = TemplateRenderer.generate_room_password("B205")
print(f"B205 password: {password_b}")  # Should be like "71025" (random digit + 0 + 1025)
```

**Expected Pattern:**
- A building: random(0-9) + "0" + (number × 4)
- B building: random(0-9) + "0" + (number × 5)

#### Test 2.3: Tag-Based Filtering
```bash
# First, add a reservation with tags
curl -X POST http://localhost:8000/api/reservations \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Test User",
    "phone": "01012345678",
    "date": "2026-02-08",
    "time": "15:00",
    "tags": "객후,1초",
    "room_number": "A101"
  }'

# Then filter by tag
curl "http://localhost:8000/campaigns/targets?tag=객후&exclude_sent=true"
```

**Expected Result:**
- Returns reservations containing "객후" tag
- Excludes those with room_sms_sent=true

#### Test 2.4: Multi-Tag Support
```bash
# Test multi-tag query
curl "http://localhost:8000/campaigns/targets?tag=1,2,2차만"
```

**Expected Result:**
- Returns reservations with ANY of: "1", "2", or "2차만" tags

### Phase 3: Notifications & Analytics

#### Test 3.1: Room Guide Sending (Manual)
```bash
curl -X POST http://localhost:8000/campaigns/notifications/room-guide \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-02-08",
    "start_row": 3,
    "end_row": 10
  }'
```

**Expected Result:**
```json
{
  "campaign_id": 1,
  "date": "2026-02-08",
  "target_count": 5,
  "sent_count": 5,
  "failed_count": 0,
  "status": "completed"
}
```

**Verify:**
- Check database: `room_sms_sent` should be true for sent reservations
- Check `campaign_logs` table for record

#### Test 3.2: Party Guide Sending
```bash
curl -X POST http://localhost:8000/campaigns/notifications/party-guide \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-02-08",
    "start_row": 100,
    "end_row": 117
  }'
```

**Expected Result:**
- Message includes participant count
- Weekend pricing if Friday/Saturday
- All unassigned guests receive message

#### Test 3.3: Gender Statistics (Mock)
```bash
# In demo mode, manually insert test data
psql -U smsuser -d smsdb

INSERT INTO gender_stats (date, male_count, female_count, total_participants)
VALUES ('2026-02-08', 15, 8, 23);

# Query via API
curl "http://localhost:8000/campaigns/gender-stats?date=2026-02-08"
```

**Expected Result:**
```json
{
  "date": "2026-02-08",
  "male_count": 15,
  "female_count": 8,
  "total_participants": 23,
  "balance": {
    "balance": "male_heavy",
    "recommendation": "Need 3 more women for balance",
    "male_pct": 65.2,
    "female_pct": 34.8
  },
  "invite_message": "현재 파티 참여 현황입니다!..."
}
```

### Phase 4: Scheduler

#### Test 4.1: List Scheduled Jobs
```bash
curl http://localhost:8000/scheduler/jobs
```

**Expected Result:**
```json
{
  "total": 3,
  "jobs": [
    {
      "id": "sync_naver_reservations",
      "name": "Sync Naver Reservations",
      "next_run": "2026-02-08T10:10:00+09:00",
      "trigger": "cron[hour='10-21', minute='*/10']"
    },
    {
      "id": "send_party_guide",
      "name": "Send Party Guide",
      "next_run": "2026-02-08T12:10:00+09:00",
      "trigger": "cron[hour='12-21', minute='10']"
    },
    {
      "id": "extract_gender_stats",
      "name": "Extract Gender Stats",
      "next_run": "2026-02-08T10:00:00+09:00",
      "trigger": "cron[hour='10-22', minute='0']"
    }
  ]
}
```

#### Test 4.2: Manual Job Trigger
```bash
# Trigger sync job manually
curl -X POST http://localhost:8000/scheduler/jobs/sync_naver_reservations/run
```

**Expected Result:**
- Job executes immediately
- Check logs for execution confirmation
- In demo mode, should create mock reservations

#### Test 4.3: Pause/Resume Job
```bash
# Pause
curl -X POST http://localhost:8000/scheduler/jobs/sync_naver_reservations/pause

# Verify paused
curl http://localhost:8000/scheduler/jobs/sync_naver_reservations

# Resume
curl -X POST http://localhost:8000/scheduler/jobs/sync_naver_reservations/resume
```

### Phase 5: Production Testing (DEMO_MODE=false)

⚠️ **WARNING:** Only proceed if you have valid credentials!

#### Test 5.1: Naver API Connection
```bash
# Set DEMO_MODE=false in .env
# Set NAVER_RESERVATION_EMAIL and NAVER_RESERVATION_PASSWORD

# Restart server
# Watch logs for connection attempt

# Manually trigger sync
curl -X POST http://localhost:8000/scheduler/jobs/sync_naver_reservations/run
```

**Success Indicators:**
- Log shows "Fetched X reservations from Naver API"
- Reservations appear in database with naver_booking_id
- No authentication errors

#### Test 5.2: Google Sheets Integration
```bash
# Set GOOGLE_SHEETS_CREDENTIALS path
# Restart server

# Test marking
curl -X POST http://localhost:8000/campaigns/notifications/room-guide \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-02-08"}'

# Verify in Google Sheets:
# - Check for "객실문자O" in memo column
```

#### Test 5.3: SMS API (Test Mode)
```bash
# Send with test mode
curl -X POST http://localhost:8000/api/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "to": "01012345678",
    "message": "Test from integrated system",
    "testmode_yn": "Y"
  }'
```

**Expected Result:**
- SMS API returns success
- Message NOT actually sent (test mode)

### Integration Testing

#### Test I1: End-to-End Room Guide Flow
```bash
# 1. Sync reservations from Naver
curl -X POST http://localhost:8000/scheduler/jobs/sync_naver_reservations/run

# 2. Wait for completion, check database
curl http://localhost:8000/api/reservations

# 3. Send room guide
curl -X POST http://localhost:8000/campaigns/notifications/room-guide \
  -d '{"date": "2026-02-08"}'

# 4. Verify marking in sheets (if production mode)
# 5. Check campaign log
curl http://localhost:8000/campaigns/campaigns/1
```

#### Test I2: Tag-Based Campaign Flow
```bash
# 1. Add tags to reservations (manually or via sync)

# 2. Preview targets
curl "http://localhost:8000/campaigns/targets?tag=객후"

# 3. Execute campaign
curl -X POST http://localhost:8000/campaigns/send-by-tag \
  -H "Content-Type: application/json" \
  -d '{
    "tag": "객후",
    "template_key": "room_guide",
    "sms_type": "room"
  }'

# 4. Verify sent status
curl "http://localhost:8000/campaigns/targets?tag=객후&exclude_sent=true"
# Should return empty (all sent)
```

## Performance Testing

### Bulk SMS Test
```bash
# Create 50 test reservations
for i in {1..50}; do
  curl -X POST http://localhost:8000/api/reservations \
    -H "Content-Type: application/json" \
    -d "{
      \"customer_name\": \"Test User $i\",
      \"phone\": \"0101234$i\",
      \"date\": \"2026-02-08\",
      \"time\": \"15:00\",
      \"room_number\": \"A$i\"
    }"
done

# Send bulk room guide
time curl -X POST http://localhost:8000/campaigns/notifications/room-guide
```

**Performance Targets:**
- 50 messages < 5 seconds
- No timeouts
- All marked correctly

## Troubleshooting

### Issue: Scheduler not starting
**Check:**
- Database connection
- Logs for errors
- Timezone settings (should be Asia/Seoul)

### Issue: Naver API authentication fails
**Check:**
- Cookie is set and not expired
- Business ID is correct (819409)
- Network access to partner.booking.naver.com

### Issue: Google Sheets "Permission denied"
**Check:**
- Service account has edit permissions on sheet
- Credentials file path is correct
- Google Sheets API enabled in GCP project

### Issue: SMS not sending
**Check:**
- API endpoint reachable (http://15.164.246.59:3000/sendMass)
- Payload format correct
- Phone numbers valid (10-11 digits, no hyphens)

## Success Criteria

✅ All tests pass
✅ Scheduler runs automatically
✅ Room guide sends correctly
✅ Party guide calculates participants
✅ Gender stats parse correctly
✅ Tag filtering works
✅ No duplicate sends
✅ Database properly tracks state

## Next Steps After Testing

1. **Frontend Integration**: Update React UI to use new endpoints
2. **Monitoring**: Set up logging and alerting
3. **Backup**: Configure database backups
4. **Production Deploy**: Use environment-specific configs
5. **Documentation**: Update user guide with new features
