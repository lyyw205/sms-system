# Consecutive Stay Helper Functions - Impact Analysis

## Current State (As of 2026-05-22)

### Reservation Model Fields (backend/app/db/models.py:38-120)
- `stay_group_id`: String, nullable, indexed — Groups by manually-linked or auto-detected consecutive stays
- `stay_group_order`: Integer, nullable — Position in group (0, 1, 2, ...)
- `is_last_in_group`: Boolean, nullable — True only for final member of group
- `is_long_stay`: Boolean, default=False — Unified flag: (stay_group_id IS NOT NULL) OR (check_out - check_in > 1 day)
- `check_in_pinned`, `check_out_pinned`: Protect manual edits from Naver sync overwrite
- `manually_extended_until`: Protects against sync overwrite on extend_stay

### ReservationSmsAssignment Model (backend/app/db/models.py:164-186)
- Unique constraint: `(reservation_id, template_key, date)` — enforces per-date dedup
- `date` field: YYYY-MM-DD, required for target_date filtering
- No direct stay_group fields

### Path A vs Path B
- **Path A**: Single Reservation record with check_out - check_in > 1 day (merged multi-day)
- **Path B**: 1-night Reservation × N records, linked via stay_group_id (split)
- Both can coexist in same group (complex scenario)

## Critical Code Locations

### SMS Chip Creation (Reconciliation)

**File: backend/app/services/chip_reconciler.py**

**Line 39-139**: `reconcile_chips_for_reservation()`
- Calls `get_schedule_dates(schedule, reservation)` to compute expected (template_key, date) pairs
- Calls `_reservation_matches_schedule()` for each date → structural filters
- Uses `ReservationSmsAssignment.date` field for per-date uniqueness

**Line 228-237**: `_reservation_matches_schedule()`
- Applies `apply_structural_filters()` with target_date parameter
- Filters must account for `target_mode` in schedule

**Line 267-293**: Special handling for `target_mode='first_night'`
```python
if target_mode == 'first_night':
    query = query.filter(Reservation.check_in_date == target_date)
    # This alone filters for check_in date, but stay_group dedup happens at
    # get_schedule_dates level (line 30-35 in schedule_utils.py)
```

### Stay-Aware Date Computation

**File: backend/app/services/schedule_utils.py**

**Line 12-47**: `get_schedule_dates(schedule, reservation)`
- **Line 18-23**: `target_mode='last_night'` — reads `is_last_in_group` field
  - Depends on: `reservation.check_out_date` or group's max checkout
  - Returns last night date only if `is_last_in_group=True` (for groups)
  - For Path B (split): Must query group members, find max checkout
- **Line 25-30**: `target_mode='first_night'` — reads `stay_group_order`
  - Returns check_in_date only if `stay_group_order == 0`
  - Skips all other group members
- **Line 32-36**: Default (None) — stay-coverage, all nights

**Observation**: This function HARDCODES dependency on `is_last_in_group` and `stay_group_order` fields.

### Template Scheduler Execution

**File: backend/app/scheduler/template_scheduler.py**

**Line 422-559**: `_get_targets_standard()`
- **Line 467**: `effective_target_mode = schedule.target_mode` (no helper call)
- **Line 477**: For `target_mode='first_night'`: adds filter `Reservation.check_in_date == target_date`
- **Line 525**: For `target_mode='last_night'`: calls `_filter_last_day()` as post-filter
- **Line 544**: Filters by `is_long_stay` for `stay_filter='exclude'`

**Line 800-847**: `_filter_last_day()`
- **Line 819-823**: Batch-queries `max(Reservation.check_out_date)` per `stay_group_id`
- **Line 828-830**: Checks if `res.check_out_date == res.check_in_date` (1-night)
- **Line 834-839**: For grouped reservations, recalculates last_day using group's max checkout
- **Observation**: Does NOT use `is_last_in_group` field — recalculates from scratch via batch query

### Consecutive Stay Linking

**File: backend/app/services/consecutive_stay.py**

**Line 27-44**: `compute_is_long_stay(res)`
```python
if res.stay_group_id:
    return True
if res.check_in_date and res.check_out_date:
    return (co - ci).days > 1  # Path A: date-diff check
```

**Line 47-242**: `detect_and_link_consecutive_stays()`
- **Line 85-100**: Scans CONFIRMED reservations within 5-day window, excludes `stay_group_excluded=True`
- **Line 128-165**: Groups by (name, phone), skips `booking_source='naver_split'` siblings
- **Line 167-188**: Builds identity-based groups, deduplicates overlapping matches
- **Line 193-228**: Detects consecutive chains within each identity group
  - **Line 197-199**: Checks `prev.check_out_date == curr.check_in_date` for continuity
  - **Line 210-221**: Assigns `stay_group_id`, `stay_group_order`, `is_last_in_group` sequentially
  - **Line 223**: Sets `is_long_stay = True` for all group members
- **Line 225-229**: Unlinks stale groups
  - Skips `manual-*` prefixed IDs (user-linked, not auto-detectable)
  - Recalculates `is_long_stay` via `compute_is_long_stay()` for unlinking members

**Critical**: This function is idempotent — reruns on every sync (Phase 4) and manual operations.

### Reservation Lifecycle

**File: backend/app/services/reservation_lifecycle.py**

**Line 24-49**: `on_dates_changed()`
- Calls `_shift_daily_records()`, `_reconcile_dates()`, then `reconcile_all_chips()`
- No explicit stay_group recalc — relies on caller (naver_sync, reservations.py) to call `detect_and_link_consecutive_stays()` later

**File: backend/app/services/naver_sync.py**

**Line 50-320**: `sync_naver_to_db()` phases:
- **Phase 3 (line 229)**: `reconcile_chips_for_reservation()` — initial chips
- **Phase 4 (line 241-242)**: `detect_and_link_consecutive_stays()` — groups reservations
- **Phase 5 (line 246)**: `auto_assign_rooms()` → reconcile (2nd) — builds room assignments

### Mutator Protection

**File: backend/app/services/reservation_mutator.py**

**Line 79-174**: `apply_changes()`
- Enforces FIELD_PERMISSIONS (NAVER vs MANUAL sources)
- For `source=MANUAL`: sets `check_in_pinned=True`, `check_out_pinned=True` automatically
- Updates `manually_edited_fields` dict with field → timestamp
- **Observation**: Does NOT touch `is_long_stay`, `stay_group_*` fields — those are computed downstream

### Room Assignment Integration

**File: backend/app/services/room_assignment.py**

**Line 52-91**: `_compute_bed_order()`
- **Line 73-76**: For Path B (split records), queries group members via `stay_group_id`
- **Line 80-86**: Reuses bed_order from previous date's same room assignment if group member found
- **Observation**: Uses `stay_group_id` directly, not a helper

### API Response Transformation

**File: backend/app/api/reservations_shared.py**

**Line 210-244**: `_to_response()`
- Computes `stay_group_total_nights` and `stay_group_night_offset` if `stay_group_id` is set
  - **Line 214-226**: Queries group members, calculates nights per member via `(check_out - check_in).days`
  - **Line 240-241**: Sets `stay_group_night_offset = cumulative` at current member
  - **Line 244**: Sets `stay_group_total_nights = total` (all members' nights summed)
- **Observation**: This duplicates night-counting logic — could be centralized in a helper

### Frontend UI Usage

**File: frontend/src/pages/RoomAssignment/components/shared/MobileGuestRow.tsx**

**Line 74-86**: Uses `stay_group_total_nights` and `stay_group_night_offset` to display "(현재박/전체박)"
- Does NOT receive `stay_group_order` or `is_last_in_group` from backend
- **Observation**: Frontend needs these fields if it wants to show stay group chain UI

---

## Proposed Helper Functions & Integration Points

### 1. `compute_total_nights(res, db) -> int`
**Purpose**: Total nights for reservation (Path A) or stay_group (Path B)

**Current Duplicates**:
- `reservations_shared.py:214-226` — computes nights per member in group
- `schedule_utils.py` — implicit in `get_schedule_dates()` logic

**Proposed Signature**:
```python
def compute_total_nights(res: Reservation, db: Session) -> int:
    """
    For Path A (single record multi-day): (check_out - check_in).days, min 1
    For Path B (stay_group_id set): sum of all member nights
    """
```

**Caller Sites**:
- `reservations_shared.py:244` — replace inline logic
- Backend response transformations (party_checkin.py, etc.)

### 2. `is_first_night(res, db, on_date) -> bool`
**Purpose**: Check if on_date is this reservation's first night

**Current State**:
- No centralized check; distributed logic in:
  - `schedule_utils.py:26-30` — only for group members, checks `stay_group_order == 0`
  - `template_scheduler.py:477` — filters by `check_in_date == target_date`
  - `room_upgrade_promise.py` — checks `target_date == check_in_date`

**Proposed Signature**:
```python
def is_first_night(res: Reservation, db: Session, on_date: str) -> bool:
    """
    True if on_date == res.check_in_date AND
    (group is empty OR res.stay_group_order == 0)
    """
```

**Callers**:
- Custom schedules (room_upgrade_promise, etc.)
- Template scheduler filtering

### 3. `is_last_night(res, db, on_date) -> bool`
**Purpose**: Check if on_date is this reservation's (or group's) last night

**Current State**:
- `template_scheduler.py:800-847` — `_filter_last_day()` recalculates per execution
- `schedule_utils.py:18-23` — reads `is_last_in_group` field only
- `room_upgrade_review.py` — similar logic

**Proposed Signature**:
```python
def is_last_night(res: Reservation, db: Session, on_date: str) -> bool:
    """
    For Path A: on_date == (checkout - 1 day)
    For Path B: on_date == (max_group_checkout - 1 day) AND is_last_in_group
    """
```

**Callers**:
- `template_scheduler.py` (replace `_filter_last_day` batch logic)
- `schedule_utils.py` (replace `is_last_in_group` hardcoding)
- Custom schedules (room_upgrade_review, etc.)

### 4. `compute_current_night(res, db, on_date) -> int`
**Purpose**: Which night is on_date? (1-indexed for UI)

**Proposed Signature**:
```python
def compute_current_night(res: Reservation, db: Session, on_date: str) -> int:
    """
    For Path A: (on_date - check_in_date).days + 1
    For Path B: sum of previous members' nights + (on_date - this member's check_in).days + 1
    Clamps to [1, total_nights]
    """
```

**Callers**:
- Frontend display (night count in guest row)
- Custom schedule logic (night-specific triggers)

### 5. `recompute_stay_metadata(res, db) -> None`
**Purpose**: Centralized recalc of stay_group_* and is_long_stay fields

**Proposed Signature**:
```python
def recompute_stay_metadata(res: Reservation, db: Session) -> None:
    """
    Recomputes is_long_stay based on (check_out - check_in > 1) OR (stay_group_id set).
    Does NOT modify stay_group_id, stay_group_order, is_last_in_group.
    Those are set only by detect_and_link_consecutive_stays() or manual API.
    Caller must db.flush() after.
    """
```

**Callers**:
- `naver_sync.py:641, 810` (after updating check_in/check_out)
- `reservations.py` (after PATCH dates)

---

## Edge Cases & Hazards

### 1. Path B (Split) + Overlapping Groups
**Scenario**: Same guest has two separate stay_group_id chains
- Example: 5/1-5/5 linked as group A, later 5/3-5/10 linked as group B (overlap)
- `detect_and_link_consecutive_stays()` **should** merge them (line 167-188 dedup logic)
- If helper doesn't account for dedup, could create false non-consecutive links

**Mitigation**: Helper must NOT modify `stay_group_id` — only read it for computations.

### 2. `is_last_in_group` Inconsistency During Unlink
**Scenario**: User unlinks member from group
- `unlink_from_group()` sets `is_last_in_group = None` on all members
- Remaining members' `is_last_in_group` must be **recalculated** via `detect_and_link_consecutive_stays()`
- If helper trusts `is_last_in_group` field without revalidation, could send to wrong target_mode

**Current State** (backend/app/api/reservations_stay.py:222-227):
```python
original.is_long_stay = compute_is_long_stay(original)
# then calls detect_and_link_consecutive_stays() to recalc group fields
```

**Mitigation**: Helper should verify `is_last_in_group` with group query, OR accept stale field as input.

### 3. Template Scheduler's _filter_last_day() Caching
**Observation**: `_filter_last_day()` (line 800-847) does batch query **per execution** (not cached)
- Computes group max_checkout **at send time**
- If reservation dates modified between chip creation (Phase 1) and sending (APScheduler), filtering could differ
- Helper MUST do same runtime query, not cache at Phase 1

**Example**: 
- Phase 1 (sync): Group has max checkout 5/5, chips created for 5/4 (last night)
- User extends one group member to 5/6
- APScheduler runs send: batch query now returns 5/6, so 5/4 filter NO LONGER matches
- Result: **Chip not sent** (consistent with extended stay) OR **wrong night filter applied**

**Mitigation**: Helper must accept on-demand `on_date` parameter, requery group state each time.

### 4. Naver Sync Overwrites stay_group_id?
**Current State** (naver_sync.py:641, 810):
- Calls `compute_is_long_stay()` to recalc boolean only
- **Does NOT call `detect_and_link_consecutive_stays()`** — that's in Phase 4, after updates
- If sync rewrites check_out_date, group chain becomes invalid, but not fixed until Phase 4

**Observation**: Helpers should NOT trigger `detect_and_link_consecutive_stays()` — that's orchestrator's job.

### 5. manually_extended_until Protection
**Field**: Reservation.manually_extended_until (set by extend_stay API)
**Purpose**: Protect extended stay from next sync overwrite

**Helper Impact**: 
- `compute_is_long_stay()` reads `check_out_date`
- If `check_out_date` was manually extended, `is_long_stay` will be True
- Helper should NOT suppress or second-guess this — trust the field

### 6. Custom Schedule Chip Pre-Send Refresh
**File**: template_scheduler.py:460-467 — `_refresh_custom_chips()`
- Calls schedule-specific reconciler (surcharge, party3, room_upgrade)
- Reconcilers query current DB state to create fresh chips
- If helper returns **stale computed value** instead of querying group at send time, could miss recent changes

**Example**: Surcharge reconciler decides whether to add "추가요금" chip
- Uses `compute_guest_count(res)` which must query group members if Path B
- If helper cached group size at Phase 1, surcharge logic breaks

**Mitigation**: Helpers must not cache — always take `db: Session` as param.

---

## Files That MUST be Updated Together

If helpers are introduced, these files must be reviewed for **simultaneous** refactoring:

1. **backend/app/services/schedule_utils.py** — `get_schedule_dates()` needs `is_first_night()`, `is_last_night()` helpers
2. **backend/app/scheduler/template_scheduler.py:800-847** — `_filter_last_day()` could delegate to `is_last_night()`
3. **backend/app/api/reservations_shared.py:210-244** — `_to_response()` could use `compute_total_nights()` helper
4. **backend/app/services/room_upgrade_*.py** — Custom schedules using target_date logic
5. **backend/app/services/consecutive_stay.py** — `detect_and_link_consecutive_stays()` owns `stay_group_*` mutations
6. **backend/app/api/reservations_stay.py** — API endpoints calling `compute_is_long_stay()`, `detect_and_link_*`
7. **backend/app/services/naver_sync.py:50-320** — Phase orchestration, must still call detect after updates

---

## Test Coverage Gaps

**Existing Tests**:
- `test_first_night_group_dedup.py` — ✅ Validates `stay_group_order=0` dedup
- `test_consecutive_stay.py` — ✅ Validates auto-detect and manual link/unlink
- `test_last_day_filter.py` — Tests `_filter_last_day()` logic

**Missing Tests** (for helper introduction):
- Path B (split) + single-day records with stay_group linked
- Path B + overlapping group membership (dedup edge case)
- `is_last_in_group` field consistency after unlink
- Custom schedule (room_upgrade_promise) with first_night + Path B
- Custom schedule (room_upgrade_review) with last_night + Path B after extend_stay
- Helper called with stale `is_last_in_group` — must revalidate from group

---

## Summary: Helper Readiness Assessment

| Helper | Complexity | Risk | Ready? |
|--------|-----------|------|--------|
| `compute_total_nights()` | Low | 🟡 Medium (Path B grouping) | **Conditional** — needs Path B test |
| `compute_current_night()` | Medium | 🟡 Medium (off-by-one night counting) | **Conditional** |
| `is_first_night()` | Medium | 🟠 High (stay_group_order dedup) | **Needs rework** — scheduler logic entangled |
| `is_last_night()` | High | 🔴 Critical (batch query cache issue) | **Requires careful timing** |
| `recompute_stay_metadata()` | Low | 🟡 Medium (lifecycle ordering) | **Ready** |

**Recommendation**: Introduce helpers **incrementally**, starting with `compute_total_nights()` and `recompute_stay_metadata()`, which are low-risk. Defer `is_last_night()` refactor until `_filter_last_day()` batch query logic is fully understood.
