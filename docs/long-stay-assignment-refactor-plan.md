# 연박자 객실 배정 시스템 리팩토링 계획안

> **목적**: 연박자 객실 배정 과정에서 발생하는 버그를 근본적으로 해결하되, Stay 테이블 도입 같은 대규모 구조 변경은 피한다.
> **전략**: 기존 구조(`Reservation` + `RoomAssignment`)를 유지하고, **단일 쓰기 경로**와 **불변식 강제**로 안정화.
> **버전**: v1 (검토용 초안, 2026-04-20 작성)

---

## 0. 현재 상태 (Baseline)

### 0-1. 이미 되어있는 것

| 영역 | 파일 | 상태 |
|---|---|---|
| 읽기 헬퍼 | `services/room_lookup.py` | `batch_room_lookup()`, `batch_room_number_map()` 존재 |
| API per-date 응답 | `api/reservations.py:277-347` | `date` 파라미터 주면 RoomAssignment가 source of truth |
| 칩 통합 로직 | `services/chip_reconciler.py` | reservation-centric + schedule-centric 양방향 구현 |
| 다중 테넌트 격리 | `db/tenant_context.py` | ContextVar 기반 자동 필터링 |
| 연박 감지 | `services/consecutive_stay.py` | 이름+전화 기반 detect_and_link, unlink |
| stay_group 선호 맵 | `room_auto_assign.py:192-229` | 전날/당일 기반 같은 방 재배정 시도 |
| 수동 배정 보호 | `room_auto_assign.py:342-356` | `assigned_by='auto'` 필터 + mid-stay 보존 |

### 0-2. 남은 문제 (확인된 버그)

| ID | 심각도 | 증상 | 위치 |
|---|---|---|---|
| **B-1** | 높음 | 체류 연장 시 새 날짜에 RoomAssignment 생성 안 됨 | `room_assignment.py:432` `reconcile_dates()` |
| **B-2** | 높음 | 네이버 동기화에서 date 변경된 예약이 Phase 5 auto-assign 대상에서 빠짐 | `naver_sync.py:232` `if added_count > 0` 조건 |
| **B-3** | 중간 | `extend_stay` API가 `assigned_by`에 username 저장 (enum 위반) | `api/reservations.py:1094, 1141` |
| **B-4** | 중간 | 자동 배정 실패(성별/용량)가 조용히 누락 — 로그/알림 없음 | `room_auto_assign.py:259, 282` silent `continue` |
| **B-5** | 중간 | `date_range()` 경계가 exclusive인 것이 문서화 안 되고 호출부 혼재 | `schedule_utils.py:52` + 호출부 |
| **B-6** | 낮음 | `Reservation.room_number` denormalized 필드가 fallback으로 남아있음 | `templates/variables.py:245,254`, `api/reservations.py:174` |
| **B-7** | 낮음 | `reconcile_dates`에 연장 케이스 테스트 없음 | `tests/integration/test_reconcile_dates.py` |
| **B-8** | 낮음 | `sync_denormalized_field()`가 check_in_date만 보는 구식 로직 남음 | `room_assignment.py:398-429` |
| **B-9** | 중간 | 매일 10:01 `daily_assign_rooms`의 DELETE+REASSIGN이 평상시 낭비이며 기존 배정을 위험에 노출 | `room_auto_assign.py:326-364` |
| **CRIT-1** | 높음 | 일반실 수동 배정 시 기존 배정자가 있어도 경고만 찍고 이중배정 진행 | `room_assignment.py:198-208` |
| **CRIT-2** | 높음 | 도미토리 수동 배정 시 용량/성별 잠금 체크 누락 | `room_assignment.py:186` (non-dorm 분기만 체크) |
| **UX-1** | 중간 | 체크아웃 당일 또는 과거 날짜로 드롭 시 혼돈 발생 | `api/reservations.py:570`, `RoomAssignment.tsx:1089` |
| **X3** | 🚨 높음 | reconcile_dates 확장이 방 충돌 미검사 → 일반실 이중배정 발생 (DB 제약 없음) | `models.py:369-371`, `room_assignment.py:reconcile_dates` |
| **D6** | 중간 | `unlink_from_group` 후 once_per_stay 중복 발송 가능 | `template_scheduler.py:496-504` |
| **S5** | 낮음 | 네이버 당일 취소 시 surcharge 칩 orphan | `naver_sync.py:470-484` |
| **D3** | 낮음 | denormalized 제거 후 빈 room_num SMS 발송 가능 | `sms_sender.py:send_single_sms` |

### 0-3. 판단: 불필요한 것으로 결론난 이슈 (참고)

분석 과정에서 나왔지만 현재 동작이 의도와 맞거나 다른 해결책으로 커버되는 이슈:

| ID | 내용 | 판단 |
|---|---|---|
| **HIGH-3** | 그룹 자동 이동이 사용자 선택 없이 실행 | 그룹=N박 연박 관점에서 현재 방식 유지 |
| **HIGH-5** | 그룹 이동 중 부분 실패 비원자적 | CRIT-1 밀어내기가 우선 적용되어 실패 자체가 없음 |
| **MED-6** | "이 날짜만" 후 그룹 연속성 반영 | `stay_group_room_map`의 dict 덮어쓰기로 "마지막 방" 이김 — 의도대로 동작 |

### 0-4. B-9 상세 분석

**현재 동작**:
```python
def daily_assign_rooms(db):
    # 오늘/내일의 auto 배정을 모두 삭제 (mid-stay만 보존)
    for target_date in [today, tomorrow]:
        auto_assignments = query.filter(assigned_by=="auto").all()
        for ra in auto_assignments:
            if not is_mid_stay(ra): delete
    # 그런 다음 auto_assign_rooms 재실행
    auto_assign_rooms(db, today)
    auto_assign_rooms(db, tomorrow)
```

**실제 효과 분석**:

| 상황 | 빈도 | DELETE의 가치 |
|---|---|---|
| 평상시 (변화 없음) | 90% | 낭비 — 다시 같은 방 배정 |
| 예약 정보 변경 (성별/인원) | 5% | 가치 있음 — 제약 재적용 |
| 방 설정 변경 (biz_item/priority) | 3% | 가치 있음 — 우선순위 재반영 |
| 재배정 실패 (성별충돌/용량) | 2% | **역효과** — 기존 배정도 증발 |

**위험 요소**:
- DELETE → INSERT 사이 "배정 없음" 창 (초 단위)
- 이 창에 SMS 스케줄러가 실행되면 "미배정"으로 오판 → 칩 생성 실패
- B-4 (silent fail) 조합 시 기존 배정 증발하고 재배정 실패 → 완전 미배정 상태

**대안 (FILL-ONLY)**:
```python
def daily_assign_rooms(db):
    # 그냥 미배정만 채워넣기
    auto_assign_rooms(db, today)
    auto_assign_rooms(db, tomorrow)
```

- `auto_assign_rooms()` 내부는 `_get_unassigned_reservations()` 사용 → 이미 fill-only
- 엣지 케이스(5%+3%)는 별도 경로로 커버 (B-9 해결책 Phase 2-5 참조)

---

### 0-5. 추가 검증 보강 사항 (v3) — Critical/High 반영

3차 검증(동시성/TZ/테넌트/성능/API계약/에러핸들링)에서 발견된 이슈를 각 Phase에 통합 반영. 이 섹션은 **모든 수정을 한 곳에 모아 추적성 확보** 목적.

#### 0-5a. Critical 4개 (반드시 반영됨)

| ID | 이슈 | 반영 위치 |
|---|---|---|
| **C-A** | reconcile_dates 충돌 체크에 FOR UPDATE 누락 → 동시 이중배정 | Phase 1-1 (FOR UPDATE 추가) |
| **C-B** | 도미토리 push-out O(N*M) 쿼리 폭증 | Phase 1-5 (batch 조회 + unique ID sync) |
| **C-C** | `update_room` response_model=RoomResponse 위반 | Phase 2-5b (RoomUpdateResponse 신규) |
| **C-D** | Push-out 루프 내 예외가 세션 오염 | Phase 1-4, 1-5 (savepoint 격리) |

#### 0-5b. High 8개 (반영됨)

| ID | 이슈 | 반영 위치 |
|---|---|---|
| **H-A** | 같은 요청 내 `today_str` 중복 계산 → 자정 경계 불일치 | 공통 패턴 (0-6d 참조) |
| **H-B** | `check_assignment_validity` N+1 쿼리 | Phase 2-5 (joinedload + batch) |
| **H-C** | Phase 1-1 INSERT가 assign_room 락 우회 | Phase 1-1 (C-A와 통합) |
| **H-D** | `ActivityLogs.tsx`에 room_assign_failed 타입 누락 | Phase 2-1 (frontend 필수 변경에 포함) |
| **H-E** | Push-out 결과 사용자에게 안 보임 | Phase 1-4, 1-5 (warnings 반환) |
| **H-F** | 밀려난 예약의 재배정 트리거 없음 | Phase 1-4, 1-5 (즉시 auto_assign_rooms 호출) |
| **H-G** | check_assignment_validity + unassign race | Phase 2-5 (flush-guard 또는 문서화) |
| **H-H** | FILL-ONLY 실패 후 5시간 공백 | Phase 2-1 SSE 알림으로 커버 |

#### 0-5c. Medium 중요 항목 (반영됨)

| ID | 이슈 | 반영 위치 |
|---|---|---|
| **M-TZ** | TimedRotatingFileHandler Docker TZ | 7-2 섹션에 TZ 환경변수 명시 |
| **M-TID** | diag_logger에 tenant_id 자동 포함 | 7-2 섹션 업데이트 |
| **M-CATCH** | check_assignment_validity 실패 시 전체 요청 블록 | Phase 2-5 try/except |
| **M-BED** | _compute_bed_order N회 호출 최적화 | Phase 1-1 (prefetch 패턴) |

#### 0-5d. 공통 패턴: `today_str` 통일 규칙 (H-A)

**원칙**: 같은 요청/잡 실행 중에는 `today_str`을 **단 1회** 계산하고 전달.

```python
# [BAD] 여러 함수에서 각자 계산 — 자정 경계 위험
def func_a():
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    ...

def func_b():
    today_str = datetime.now(KST).strftime("%Y-%m-%d")  # 다른 시점일 수 있음
    ...

# [GOOD] 진입점에서 1회 계산, 파라미터로 전달
def endpoint_handler(...):
    today_str = datetime.now(KST).strftime("%Y-%m-%d")  # 여기서만
    func_a(..., today_str=today_str)
    func_b(..., today_str=today_str)
```

**적용 대상**:
- `reconcile_dates()` — 호출자가 today_str 파라미터로 전달
- `assign_room()` 내 1-4 밀어내기 — 진입 시 1회 계산
- `_assign_all_rooms()` 내 1-5 강경책 — 진입 시 1회 계산
- `_update_reservation()` (naver_sync) — 루프 전 1회 계산

---

## 1. 불변식 (Invariants) 정의

리팩토링 후 **반드시 지켜져야 할 규칙**. 모든 수정의 기준점.

```
[INV-1] RoomAssignment 커버리지
    모든 CONFIRMED 예약에 대해:
    RoomAssignment.date 집합 == date_range(check_in, check_out)
    (단, 자동배정 실패 시 부분 커버는 허용하되 로그 남김)

[INV-2] assigned_by 값 제약
    RoomAssignment.assigned_by ∈ {"auto", "manual"}
    (이외 값은 DB 제약 수준으로 차단 or 코드 어설션)

[INV-3] 날짜 경계 일관성
    _date_range(from, to) = [from, to)  (end-exclusive, 현재 그대로)
    → 모든 호출부는 end_date를 "체크아웃 당일"로 전달해야 함

[INV-4] 배정 실패 가시성
    auto_assign에서 배정 실패 시 반드시 ActivityLog 생성
    (예약 미배정 상태 추적 가능)

[PRIORITY-1] 연박/연장 예약자 우선
    연박자의 방은 체류 기간 내내 유지되어야 한다.
    연장 시 새 날짜에 충돌 발생하면 충돌하는 예약자를 미배정으로 밀어낸다.
    근거: 연박자는 체류 중 방 혼란 시 운영적 리스크 크고,
          1박 예약자는 다음 auto_assign에서 다른 방으로 재배정 가능.

[PRIORITY-2] 운영자 수동 배정도 동일하게 우선
    assigned_by="manual" 레코드는 시스템이 자동으로 덮어쓰지 않는다.
    (daily_assign_rooms의 `assigned_by == "auto"` 필터로 이미 강제됨)
```

---

## 2. Phase 별 작업 계획

### Phase 0 — 잔재 테이블/컬럼 사전 정리 (1일)

**목적**: 코드베이스에 남아있는 완전히 dead한 테이블/컬럼을 제거해 향후 리팩토링 범위 축소.

**발견 경위**: Change Validator 검증 중 Architect가 전수 조사. 모두 read/write 0건 확인됨.

#### 0-a. 제거 대상 (5개)

| 대상 | 위치 | 현재 상태 | 비고 |
|---|---|---|---|
| `CampaignLog` 테이블 | `models.py:240-257` | DEPRECATED 주석 + 0건 INSERT/SELECT | ActivityLog로 완전 대체 |
| `Rule` 테이블 | `models.py:147-160` | DEACTIVATED 주석 + `api/rules.py` 없음 | LLM 자동응답 기능 제거됨 |
| `Document` 테이블 | `models.py:163-175` | DEACTIVATED 주석 + `api/documents.py` 없음 | RAG 기능 제거됨 |
| `GenderStat` 테이블 | `models.py:260-271` | 0건 사용 | `ParticipantSnapshot`으로 완전 대체 |
| `Tenant.snapshot_refresh_times` 컬럼 | `models.py:569` | 0건 read/write | 정의만 있음 |

#### 0-b. 작업 내용

1. **Alembic 마이그레이션 신규 1개**:
```python
def upgrade():
    op.drop_table('campaign_logs')
    op.drop_table('rules')
    op.drop_table('documents')
    op.drop_table('gender_stats')
    op.drop_column('tenants', 'snapshot_refresh_times')

def downgrade():
    # rollback: 테이블 재생성 (데이터 없이 구조만)
    ...
```

2. **모델 클래스 제거**:
- `backend/app/db/models.py`: `CampaignLog`, `Rule`, `Document`, `GenderStat` 클래스 삭제
- `Tenant` 클래스의 `snapshot_refresh_times` Column 삭제

3. **TENANT_MODELS 등록 해제** (`models.py:654-660`):
```python
for _model in [
    Message, Reservation, MessageTemplate, ReservationSmsAssignment,
    # Rule, Document, CampaignLog, GenderStat — 제거됨
    RoomBizItemLink, Building, RoomGroup, Room, RoomAssignment,
    NaverBizItem, TemplateSchedule, ActivityLog, PartyCheckin, ReservationDailyInfo,
    ParticipantSnapshot, OnsiteSale, DailyHost, OnsiteAuction, PartyHost,
]:
    _register(_model)
```

4. **database.py runtime migration 정리** (있다면): `snapshot_refresh_times` 관련 auto-migration 코드 제거

5. **테스트 정리**: 혹시 해당 모델 참조하는 테스트 있으면 제거

#### 0-c. 안전성 검증

배포 직전 grep 재확인:
```bash
grep -rn "CampaignLog\|Rule\b\|Document\b\|GenderStat\|snapshot_refresh_times" \
  backend/app/ backend/tests/ frontend/src/
```
결과 예상: 0건 (models.py 제거 후).

**배포 순서**: Phase 0 배포 → 안정 확인 → Phase 1 배포.

---

### Phase 1 — 핵심 버그 직접 수정 (우선순위 최상, 7일)

#### 1-1. `reconcile_dates()` 확장 [B-1 해결]

**파일**: `backend/app/services/room_assignment.py:432-466`

**Before (현재)**:
```python
def reconcile_dates(db, reservation):
    valid_dates = set(_date_range(check_in, check_out))
    # 범위 밖 RoomAssignment 삭제만
    orphaned = query.filter(~RoomAssignment.date.in_(valid_dates)).all()
    for a in orphaned:
        db.delete(a)
```

**After (수정안)**:
```python
def reconcile_dates(db, reservation):
    valid_dates = set(_date_range(check_in, check_out))
    if not valid_dates: return

    # 1) 범위 밖 삭제 (기존 로직)
    orphaned = query.filter(~RoomAssignment.date.in_(valid_dates)).all()
    for a in orphaned: db.delete(a)

    # 2) 범위 내 누락 날짜 채우기 (NEW)
    existing = query.filter(RoomAssignment.date.in_(valid_dates)).all()
    existing_dates = {a.date for a in existing}
    missing = valid_dates - existing_dates

    if missing and existing:
        # 같은 reservation의 가장 가까운 배정을 복사 (방 유지)
        reference = min(existing, key=lambda a: abs(
            (datetime.strptime(a.date, "%Y-%m-%d") -
             datetime.strptime(reservation.check_in_date, "%Y-%m-%d")).days
        ))
        ref_room = db.query(Room).get(reference.room_id)
        today_str = datetime.now(KST).strftime("%Y-%m-%d")

        for d in sorted(missing):
            # ★ X3 수정: 충돌 체크 — [PRIORITY-1] 연박자 우선, 충돌자 밀어내기
            # ★ C-A/H-C 반영: 일반실은 FOR UPDATE로 동시성 보호 (assign_room과 동일 패턴)
            conflict_query = db.query(RoomAssignment).filter(
                RoomAssignment.room_id == reference.room_id,
                RoomAssignment.date == d,
                RoomAssignment.reservation_id != reservation.id,
            )
            if not ref_room.is_dormitory:
                conflict_query = conflict_query.with_for_update()
            conflicts = conflict_query.all()

            if conflicts and d > today_str:
                # 미래 날짜에 충돌 — 연장 중인 예약자(reservation) 우선
                # 충돌자를 미배정으로 밀어냄 (Phase 1-4/1-5와 동일 정책)
                for c_ra in conflicts:
                    c_res = db.query(Reservation).get(c_ra.reservation_id)
                    c_pushed_id = c_ra.reservation_id
                    if c_res:
                        c_res.section = "unassigned"
                    db.delete(c_ra)
                    db.flush()

                    # 밀려난 예약의 칩/surcharge 정리
                    try:
                        sync_sms_tags(db, c_pushed_id)
                    except Exception as e:
                        logger.warning(f"Extension push-out sync_sms_tags failed: {e}")
                    try:
                        from app.services.surcharge import _delete_all_surcharge_chips
                        _delete_all_surcharge_chips(db, c_pushed_id, d)
                    except Exception as e:
                        logger.warning(f"Extension push-out surcharge cleanup failed: {e}")

                    log_activity(
                        db, type="room_move",
                        title=f"[{c_res.customer_name if c_res else '?'}] 연박 연장에 밀림 — 미배정 이동 ({d})",
                        detail={
                            "reservation_id": c_pushed_id,
                            "date": d,
                            "cause": "long_stay_extension_priority",
                            "caused_by_reservation_id": reservation.id,
                            "caused_by_customer": reservation.customer_name,
                        },
                        created_by="system",
                    )
            elif conflicts and d <= today_str:
                # 당일/과거 충돌은 밀어내지 않음 (당일 이중배정 허용 정책과 일치)
                logger.warning(
                    f"reconcile_dates: conflict on {d} not pushed (today/past). "
                    f"manual review needed for res={reservation.id}"
                )

            # 새 RoomAssignment INSERT
            new_ra = RoomAssignment(
                reservation_id=reservation.id,
                date=d,
                room_id=reference.room_id,
                room_password=reference.room_password,
                room_password_prefixed=reference.room_password_prefixed,
                assigned_by=reference.assigned_by,
                bed_order=_compute_bed_order(db, reservation.id, reference.room_id, d, ref_room),
            )
            db.add(new_ra)
        db.flush()

        # ★ 검증 반영 (H-1): surcharge reconcile
        try:
            from app.services.surcharge import reconcile_surcharge
            for d in sorted(missing):
                reconcile_surcharge(db, reservation.id, d, room_id=reference.room_id)
        except Exception as e:
            logger.warning(f"Surcharge reconcile failed in reconcile_dates: {e}")

    if orphaned or missing:
        sync_sms_tags(db, reservation.id)  # 칩 재계산
```

**검증 반영 (H-1, H-2)**: bed_order는 `_compute_bed_order` 로 재계산 + 새 날짜에 surcharge reconcile 호출.

**테스트 추가**:
```python
# test_reconcile_dates.py에 신규 케이스
def test_extended_stay_fills_missing_dates(self, db):
    """2박 → 3박으로 연장 시 3일째 RoomAssignment 자동 생성."""

def test_extended_stay_preserves_existing_room(self, db):
    """연장 시 기존 배정된 방을 그대로 이어받는다."""

def test_extended_stay_uses_nearest_reference(self, db):
    """중간 방 변경(4/10=A, 4/11=B) 후 연장 시 B방을 복사."""
```

---

#### 1-2. `naver_sync` Phase 5 트리거 확장 [B-2 해결]

**파일**: `backend/app/services/naver_sync.py:232-253`

**Before**:
```python
if added_count > 0:  # updated는 안 보임
    try:
        dates = set()
        for res_data in reservations:
            d = res_data.get("date")
            ...
```

**After**:
```python
# date_changed_ids는 Phase 2에서 이미 수집됨 (line 182-194)
if added_count > 0 or date_changed_ids:  # 변경된 예약도 포함
    try:
        # date_changed_ids에 해당하는 예약들의 전체 체류 범위 수집
        changed_reservations = db.query(Reservation).filter(
            Reservation.id.in_(date_changed_ids)
        ).all() if date_changed_ids else []

        dates = set()
        # added: 기존 로직 유지
        for res_data in reservations:
            if res_data.get("external_id") in new_external_ids:
                d = res_data.get("date")
                if d and (d > today or reconcile_date):
                    dates.add(d)

        # date_changed: 전체 체류 범위의 모든 날짜 추가 (NEW)
        for res in changed_reservations:
            if res.check_in_date and res.check_out_date:
                for d in _date_range(res.check_in_date, res.check_out_date):
                    if d >= today:  # 과거는 건드리지 않음
                        dates.add(d)

        for d in sorted(dates):
            auto_assign_rooms(db, d, created_by="sync")
```

**테스트 추가**:
```python
# test_naver_sync_extend.py 신규 파일
def test_extended_reservation_gets_new_dates_assigned(db, mock_provider):
    """네이버 동기화로 check_out_date가 연장되면 새 날짜 auto-assign 실행."""
```

---

#### 1-3. `extend_stay` API의 `assigned_by` 값 수정 [B-3 해결]

**파일**: `backend/app/api/reservations.py:1094, 1141`

**Before**:
```python
assign_room(
    db, new_res.id, request.room_id, next_date_str,
    assigned_by=current_user.username,  # 잘못됨
)
```

**After**:
```python
assign_room(
    db, new_res.id, request.room_id, next_date_str,
    assigned_by="manual",  # enum 값 고정
    created_by=current_user.username,  # 감사 로그용
)
```

동일 수정 2곳 (line 1094, 1141).

**기존 데이터 정리** (선택, 1회성 스크립트):
```sql
UPDATE room_assignments
SET assigned_by = 'manual'
WHERE assigned_by NOT IN ('auto', 'manual');
```

---

#### 1-4. 미래 날짜 이중배정 시 기존 배정자 밀어내기 [CRIT-1 해결]

**파일**: `backend/app/services/room_assignment.py:186-208`

**정책**:
- 당일(`d <= today`): 기존 경고 로직 유지 (의도적 수동 이중배정 허용)
- 미래(`d > today`): 기존 배정자를 미배정(`section="unassigned"`)으로 밀어내고 RoomAssignment 삭제
- 근거: 다음날 10:01 `daily_assign_rooms`(B-9 이후엔 FILL-ONLY)가 미배정자 자동 재배정

**Before**:
```python
if not is_dorm:
    for d in dates:
        existing = (...).first()
        if existing:
            if assigned_by == "auto":
                raise ValueError(...)
            # manual은 경고만 — 이중배정 허용
            logger.warning(...)
```

**After**:
```python
if not is_dorm:
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    for d in dates:
        existing = (...).first()
        if not existing: continue

        if assigned_by == "auto":
            raise ValueError(...)

        # manual: 당일은 허용, 미래는 밀어내기
        if d <= today_str:
            logger.warning(f"Manual double-booking on today: {d}")
        else:
            # 미래 이중배정 → 기존 예약자 미배정 처리
            other_res = db.query(Reservation).get(existing.reservation_id)
            pushed_res_id = existing.reservation_id
            if other_res:
                other_res.section = "unassigned"
            db.delete(existing)
            db.flush()

            # ★ 검증 반영 (C-1, H-3): 밀려난 예약의 SMS 칩 + surcharge 정리
            # 없으면 방 없는 채 room_guide SMS 발송되거나 orphan surcharge 칩 남음
            try:
                sync_sms_tags(db, pushed_res_id)
            except Exception as e:
                logger.warning(f"Pushed-out sync_sms_tags failed: {e}")
            try:
                from app.services.surcharge import _delete_all_surcharge_chips
                _delete_all_surcharge_chips(db, pushed_res_id, d)
            except Exception as e:
                logger.warning(f"Pushed-out surcharge cleanup failed: {e}")

            log_activity(
                db, type="room_move",
                title=f"[{other_res.customer_name}] 이중배정 회피 — 미배정 이동 ({d})",
                detail={
                    "reservation_id": pushed_res_id,
                    "date": d,
                    "cause": "pushed_out_by",
                    "pushed_out_by_reservation_id": reservation_id,
                },
                created_by="system",
            )
```

**검증 반영 (C-1, H-3)**: 밀려난 예약의 `sync_sms_tags` 호출로 stale room_guide 칩 제거 + surcharge 칩 정리.

**검증 반영 추가 (C-D, H-E, H-F)**:
```python
# assign_room 함수 시그니처 확장: push_out_info 리턴
def assign_room(...) -> Tuple[List[RoomAssignment], List[Dict]]:
    pushed_out = []  # [{reservation_id, customer_name, date, cause}, ...]
    ...
    # C-D: savepoint로 개별 push-out 격리
    for d in dates:
        existing = ...
        if existing and d > today_str:
            savepoint = db.begin_nested()
            try:
                # push-out 로직 (기존 코드)
                ...
                pushed_out.append({
                    "reservation_id": pushed_res_id,
                    "customer_name": other_res.customer_name,
                    "date": d,
                })
                savepoint.commit()
            except Exception as e:
                savepoint.rollback()
                logger.error(f"Push-out failed for res={pushed_res_id}: {e}")
                # 루프 계속 — 한 명 실패가 전체 막지 않음
    
    # H-F: 밀려난 예약의 즉시 재배정 시도
    affected_dates = {p["date"] for p in pushed_out}
    for d in affected_dates:
        try:
            from app.services.room_auto_assign import auto_assign_rooms
            auto_assign_rooms(db, d, created_by="pushed_out_retrigger")
        except Exception as e:
            logger.warning(f"Re-assign trigger failed for {d}: {e}")
    
    return assignments, pushed_out  # API에서 warnings로 반환
```

**API 엔드포인트** (`api/reservations.py:605`): pushed_out 정보를 `warnings`에 추가하여 프론트 표시.
```python
assignments, pushed_out = room_assignment.assign_room(...)
for p in pushed_out:
    warnings.append(f"{p['customer_name']} ({p['date']})가 미배정으로 이동됨")
```

**테스트**:
```python
def test_future_conflict_pushes_existing_to_unassigned(db):
    """미래 날짜에 다른 예약자가 있는 방으로 이동 시 기존 예약자가 미배정으로 밀려남."""

def test_today_conflict_still_allows_double_booking(db):
    """당일 이중배정은 여전히 허용 (경고만)."""

def test_pushed_out_reservation_section_updated(db):
    """밀려난 예약의 section이 'unassigned'로 변경됨."""
```

---

#### 1-5. 도미토리 혼성/용량 체크 + 강경책 밀어내기 [CRIT-2 해결]

**파일**: `backend/app/services/room_assignment.py:186` (is_dorm 분기 신설)

**정책 (옵션 3a 강경책)**:
- 수동 드래그 시에도 도미토리 제약 체크 (기존: auto만 체크)
- 미래 날짜 혼성 발생: 기존 멤버 **전부** 미배정으로
- 미래 날짜 용량 초과: 기존 멤버 전부 미배정으로
- 당일(`d <= today`): 기존처럼 경고만 (운영 현장 수동 조정 여지)

**Before**:
```python
# 도미토리는 concurrency guard 건너뜀 — 체크 없음
if not is_dorm:
    for d in dates: check_conflict()
# is_dorm이면 아무 체크도 없이 INSERT
```

**After**:
```python
if is_dorm and assigned_by == "manual":
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    new_gender = (reservation.gender or "").strip()
    new_count = reservation.party_size or reservation.booking_count or 1

    for d in dates:
        if d <= today_str: continue  # 당일은 건드리지 않음

        others = db.query(RoomAssignment).filter(
            RoomAssignment.room_id == room_id,
            RoomAssignment.date == d,
            RoomAssignment.reservation_id != reservation_id,
        ).all()
        if not others: continue

        # 혼성 체크
        gender_conflict = False
        if new_gender:
            for o_ra in others:
                o_res = db.query(Reservation).get(o_ra.reservation_id)
                o_gender = (o_res.gender or "").strip() if o_res else ""
                if o_gender and o_gender != new_gender:
                    gender_conflict = True; break

        # 용량 체크
        total_occupancy = sum(
            (db.query(Reservation).get(o.reservation_id).party_size or 1)
            for o in others
        )
        capacity_exceeded = (total_occupancy + new_count) > room_obj.bed_capacity

        # 강경책: 기존 멤버 전부 미배정으로
        if gender_conflict or capacity_exceeded:
            reason = "gender_mix" if gender_conflict else "capacity"
            pushed_res_ids = [o.reservation_id for o in others]
            for o_ra in others:
                o_res = db.query(Reservation).get(o_ra.reservation_id)
                if o_res: o_res.section = "unassigned"
                db.delete(o_ra)
            db.flush()

            # ★ 검증 반영 (C-1, H-3): 밀려난 예약 각자의 SMS 칩/surcharge 정리
            for p_id in pushed_res_ids:
                try:
                    sync_sms_tags(db, p_id)
                except Exception as e:
                    logger.warning(f"Dorm pushed-out sync_sms_tags failed: {e}")
                try:
                    from app.services.surcharge import _delete_all_surcharge_chips
                    _delete_all_surcharge_chips(db, p_id, d)
                except Exception as e:
                    logger.warning(f"Dorm pushed-out surcharge cleanup failed: {e}")

            log_activity(
                db, type="room_move",
                title=f"도미토리 제약 충돌 — {len(others)}명 미배정 이동 ({d})",
                detail={
                    "room_id": room_id,
                    "date": d,
                    "reason": reason,
                    "pushed_count": len(others),
                    "pushed_reservation_ids": pushed_res_ids,
                    "caused_by_reservation_id": reservation_id,
                },
                created_by="system",
            )
```

**검증 반영 (C-1, H-3)**: 밀려난 예약 각자에 대해 `sync_sms_tags` + surcharge 정리.

**검증 반영 추가 (C-B 배치 최적화, C-D savepoint, H-E warnings)**:
```python
# 도미토리 강경책: 배치 최적화 + savepoint 격리

if is_dorm and assigned_by == "manual":
    today_str = ...  # H-A: 루프 전 1회 계산
    
    # C-B 최적화: 전체 dates의 others를 한 번에 조회
    all_others = db.query(RoomAssignment).filter(
        RoomAssignment.room_id == room_id,
        RoomAssignment.date.in_([d for d in dates if d > today_str]),
        RoomAssignment.reservation_id != reservation_id,
    ).all()
    
    # Reservation 정보도 배치로
    other_res_ids = {o.reservation_id for o in all_others}
    other_res_map = {
        r.id: r for r in db.query(Reservation).filter(
            Reservation.id.in_(other_res_ids)
        ).all()
    }
    
    # 날짜별 그룹핑
    from collections import defaultdict
    others_by_date = defaultdict(list)
    for o in all_others:
        others_by_date[o.date].append(o)
    
    all_pushed_res_ids = set()  # 중복 sync_sms_tags 방지
    
    for d in sorted(dates):
        if d <= today_str: continue
        others = others_by_date.get(d, [])
        if not others: continue
        
        # 혼성/용량 체크 (동일 로직)
        ...
        
        if gender_conflict or capacity_exceeded:
            # C-D: savepoint로 격리
            savepoint = db.begin_nested()
            try:
                for o_ra in others:
                    o_res = other_res_map.get(o_ra.reservation_id)
                    if o_res: o_res.section = "unassigned"
                    db.delete(o_ra)
                    all_pushed_res_ids.add(o_ra.reservation_id)
                db.flush()
                savepoint.commit()
            except Exception as e:
                savepoint.rollback()
                logger.error(f"Dorm hardline savepoint failed for {d}: {e}")
                continue
    
    # C-B: unique reservation ID별 1회 sync_sms_tags (중복 제거)
    for p_id in all_pushed_res_ids:
        try:
            sync_sms_tags(db, p_id)
        except Exception as e:
            logger.warning(f"Dorm push-out sync failed for res={p_id}: {e}")
    
    # surcharge는 (res_id, date) 단위 — 날짜별 호출 필요
    ...
```

**효과**: 8명×5일 push-out 시 쿼리 수:
- 기존: 8×5 (others) + 8×5 (Reservation) + 8×5 (sync) = 120+ 쿼리
- 최적화: 1 (batch others) + 1 (batch Res) + 8 (unique sync) = **10 쿼리**

**테스트**:
```python
def test_dormitory_gender_conflict_pushes_all_existing(db):
    """도미토리에 성별 다른 예약자가 있으면 기존 멤버 전부 미배정."""

def test_dormitory_capacity_overflow_pushes_all_existing(db):
    """도미토리 용량 초과 시 기존 멤버 전부 미배정."""

def test_dormitory_same_gender_no_push(db):
    """성별 같고 용량 여유 있으면 공동 입실 유지."""
```

---

#### 1-6. "오늘 이후 전체" + 과거 드롭 차단 [UX-1 해결]

**Backend** — `backend/app/api/reservations.py:568-580`:
```python
today_str = datetime.now(KST).strftime("%Y-%m-%d")
from_date = req_date or db_reservation.check_in_date

# ★ 검증 반영 (M-1): 양쪽 분기 모두 과거 날짜 차단 (API 직접 호출 방어)
if from_date < today_str:
    raise HTTPException(
        status_code=400,
        detail="지난 날짜의 배정은 수정할 수 없습니다"
    )

if apply_subsequent:
    end_date = db_reservation.check_out_date
else:
    end_date = None

room_assignment.assign_room(
    db, reservation_id, room_id,
    from_date, end_date, ...
)
```

**검증 반영 (M-1)**: `apply_subsequent=false`일 때도 백엔드에서 과거 날짜 차단.

**Frontend** — `RoomAssignment.tsx:1089` handleDropOnRoom 시작 부분:
```javascript
const handleDropOnRoom = (resId, roomId, dropTargetDate) => {
  const targetDate = dropTargetDate || selectedDate;

  // 과거 날짜 드롭 차단
  if (targetDate.isBefore(dayjs(), 'day')) {
    toast.warning('지난 날짜의 배정은 수정할 수 없습니다');
    return;
  }
  // ... 기존 로직
};
```

**Frontend 모달 라벨 변경** — `RoomAssignment.tsx:3213, 3219`:
```
Before:
  [전체 날짜 적용] [오늘만 적용] [취소]

After:
  [오늘 이후 전체] [이 날짜만] [취소]
```

**멘탈 모델 명확화**:
- "오늘 이후 전체" = 선택한 날짜가 오늘 이상이면 그 날부터 체크아웃까지, 과거면 오늘부터
- "이 날짜만" = 드롭한 그 한 날짜만 (이전 이름 "오늘만"의 혼동 제거)

---

### Phase 2 — 가시성 & 일관성 (1주)

#### 2-1. 배정 실패 명시화 [B-4 해결]

**파일**: `backend/app/services/room_auto_assign.py:247-321`

silent continue 2곳을 수집으로 변경:

```python
def _assign_all_rooms(...) -> Tuple[List[dict], List[dict]]:
    """Returns (assigned, failed)"""
    assigned_results = []
    failed_results = []  # NEW

    for res in candidates:
        candidate_rooms = biz_to_rooms.get(res.naver_biz_item_id, [])
        if not candidate_rooms:
            failed_results.append({
                "reservation_id": res.id,
                "customer_name": res.customer_name,
                "reason": "no_candidate_rooms",
                "biz_item_id": res.naver_biz_item_id,
            })
            continue

        # ... 기존 로직 ...
        # 성별/용량 실패 시:
        last_failure_reason = None
        for room in candidate_rooms:
            if room.is_dormitory:
                if not check_capacity:
                    last_failure_reason = "capacity_full"; continue
                if gender_conflict:
                    last_failure_reason = "gender_lock"; continue
            ...
        else:  # for-else: 모든 방 실패
            failed_results.append({
                "reservation_id": res.id,
                "customer_name": res.customer_name,
                "reason": last_failure_reason or "unknown",
            })

    return assigned_results, failed_results
```

**`auto_assign_rooms()`에서 로깅**:
```python
assigned_details, failed_details = _assign_all_rooms(...)

if failed_details:
    log_activity(
        db, type="room_assign_failed",
        title=f"객실 자동 배정 실패 {len(failed_details)}건 ({target_date})",
        detail={"target_date": target_date, "failures": failed_details},
        target_count=len(failed_details),
        failed_count=len(failed_details),
        status="failed",
        created_by=created_by,
    )
    # SSE 이벤트
    from app.services.event_bus import publish
    publish("room_assign_failed", {
        "target_date": target_date,
        "count": len(failed_details),
    }, tenant_id=current_tenant_id.get())
```

**프론트 필수 변경** (검증 반영 G, M-2, H-D):
- `RoomAssignment.tsx:800-810` SSE 리스너에 `room_assign_failed` 핸들러 추가 → toast 알림
- `ActivityLogs.tsx` 업데이트 (H-D 반영):
  - `ActivityType` union (`ActivityLogs.tsx:29-35`)에 `'room_assign_failed'` 추가
  - `TYPE_LABELS` (line 60-66)에 `room_assign_failed: '배정 실패'` 추가
  - `TYPE_BADGE_COLOR` (line 68-74)에 `room_assign_failed: 'failure'` 추가
  - 필터 `<option>` (line 295)에 추가
  - 상세 렌더링: `detail.failures` 배열 표시 (이름, 사유, 날짜)

**실패 사유 분류** (검증 반영 G — Regular room 케이스 추가):
```
- no_candidate_rooms   : biz_item_id에 매칭되는 방 없음
- capacity_full        : 도미토리 용량 초과
- gender_lock          : 도미토리 성별 충돌
- all_rooms_occupied   : 일반실이 모두 이미 배정됨 ← 추가
- unknown              : 기타
```

Regular room 분기의 for-else 패턴:
```python
# room_auto_assign.py:295-321 수정
for reg_room in candidate_rooms:
    if rooms_assigned >= rooms_needed: break
    ...
else:
    # 모든 candidate_rooms를 순회했지만 할당 못함
    if rooms_assigned < rooms_needed:
        failed_results.append({
            "reservation_id": res.id,
            "reason": "all_rooms_occupied",
        })
```

---

#### 2-2. `date_range` 경계 명시화 [B-5 해결]

**파일**: `backend/app/services/schedule_utils.py:52`

docstring 명시 + 타입 힌트 강화:
```python
def date_range(from_date: str, end_date: Optional[str]) -> List[str]:
    """Generate dates in [from_date, end_date) — end_date EXCLUSIVE.

    For a stay: pass check_in_date as from_date and check_out_date as end_date.
    The returned list covers all NIGHTS (체류 일수), not including checkout day.

    If end_date is None or <= from_date: returns [from_date].
    """
```

**호출부 감사** (모든 call site 주석 추가):
- `room_assignment.py:176, 330, 371` — check_out_date 전달 (OK)
- `reservations.py:498` — date_range(check_in, check_out) (OK)
- `schedule_utils.py:43` — date_range(check_in, check_out) (OK)
- 모두 현재 정상. 하지만 향후 실수 방지용 docstring 강화만.

---

#### 2-3. 직접 SQL DELETE → clear_all_for_reservation 교체 (타겟 수정)

**변경 사유** (검증 반영 M-3): 원래 "facade 도입 (필수)" 이었으나, 검증 결과 facade가 순수 delegation이라 코드 부풀림 대비 가치 낮음. 진짜 문제는 직접 SQL DELETE 2곳의 중복 로직 → **타겟 수정으로 전환**.

**수정 1**: `api/reservations.py:528` (delete_reservation)
```python
# Before
db.query(RoomAssignment).filter(
    RoomAssignment.reservation_id == reservation_id, 
    RoomAssignment.tenant_id == tid
).delete()

# After
from app.services.room_assignment import clear_all_for_reservation
clear_all_for_reservation(db, reservation_id)
```

**수정 2**: `api/reservations.py:1185` (cancel_extend_stay)
```python
# Before
db.query(RoomAssignment).filter(
    RoomAssignment.reservation_id == extended.id, 
    RoomAssignment.tenant_id == tid
).delete()

# After
clear_all_for_reservation(db, extended.id)
```

**기대 효과**:
- SMS 칩/surcharge 정리 부재 문제 해결 (clear_all 내부에서 cleanup)
- 쓰기 경로 분산 문제 완화 (facade 도입 없이도)
- 코드 부풀림 없음 (2줄 교체)

**facade 도입은 폐기** — 필요해지면 Phase 2-5 invariant 체크를 상위 레벨에서 강제할 때 재논의.

**수정 3 추가** (검증 반영 S5): `naver_sync.py:470-474` 당일 취소 경로
```python
# 기존: 직접 SQL DELETE + room_number/password=None (원래 코드 유지)
# 추가: 영향 날짜의 surcharge 칩도 정리
affected_dates = [
    ra.date for ra in db.query(RA).filter(
        RA.reservation_id == existing.id,
        RA.tenant_id == tid,
        RA.date >= today_str,
    ).all()
]
db.query(RA).filter(...).delete()

# ★ 검증 반영 (S5): surcharge 칩 정리
from app.services.surcharge import _delete_all_surcharge_chips
for d in affected_dates:
    _delete_all_surcharge_chips(db, existing.id, d)
```

---

#### 2-4. `daily_assign_rooms` FILL-ONLY 전환 [B-9 해결]

**파일**: `backend/app/services/room_auto_assign.py:326-364`

**Before (현재 — DELETE + REASSIGN)**:
```python
def daily_assign_rooms(db):
    today = ...; tomorrow = ...
    tid = current_tenant_id.get()

    for target_date in [today, tomorrow]:
        auto_assignments = query.filter(
            RA.date == target_date,
            RA.assigned_by == "auto",
        ).all()
        delete_ids = []
        for ra in auto_assignments:
            res = ...
            if is_mid_stay(res, target_date): continue
            delete_ids.append(ra.id)
        if delete_ids:
            query.filter(RA.id.in_(delete_ids)).delete(...)
    db.flush()

    auto_assign_rooms(db, today, created_by="scheduler")
    auto_assign_rooms(db, tomorrow, created_by="scheduler")
```

**After (FILL-ONLY)**:
```python
def daily_assign_rooms(db):
    """미배정 예약만 채워넣기. 기존 배정은 건드리지 않음.

    설계 근거:
      - 평상시: 어제와 같은 방이 그대로 유지됨 (변경 불필요)
      - 예약 정보 변경 시: update_reservation에서 명시적으로 reconcile (Phase 2-5)
      - 방 설정 변경 시: 수동 재배정 버튼 또는 API 유도
      - DELETE 창에서의 레이스 컨디션 제거
    """
    today = datetime.now(KST).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(KST) + timedelta(days=1)).strftime("%Y-%m-%d")

    result_today = auto_assign_rooms(db, today, created_by="scheduler")
    result_tomorrow = auto_assign_rooms(db, tomorrow, created_by="scheduler")

    return {"today": result_today, "tomorrow": result_tomorrow}
```

**안전장치 (점진 전환)**:

환경변수로 A/B 비교 가능하게 구현:
```python
import os
_MODE = os.environ.get("DAILY_REASSIGN_MODE", "aggressive")  # "aggressive" | "conservative"

def daily_assign_rooms(db):
    if _MODE == "conservative":
        # FILL-ONLY
        ...
    else:
        # 기존 DELETE + REASSIGN (로깅 강화)
        ...
        logger.info(f"[daily_reassign] would_delete={len(delete_ids)} target={target_date}")
```

**롤아웃 절차**:
1. Phase 2 배포: 기본값 `aggressive`, 로깅 강화
2. 1-2주 관찰: 실제로 몇 건이 "방이 바뀌었는지" 데이터 수집
3. 데이터 기반 판단 → `conservative`로 전환
4. 1-2주 추가 관찰 후 aggressive 로직 완전 제거

---

#### 2-5. 예약/방 설정 변경 시 명시적 reconcile [B-9 엣지 케이스 커버]

B-9 FILL-ONLY 전환 시 놓치는 8% 엣지 케이스를 각 진입점에서 처리.

##### 2-5a. 예약 정보 변경 (성별/인원)

**파일**: `backend/app/api/reservations.py:474-489` (update_reservation)

**추가 로직**:
```python
# 기존 코드 아래에 추가
_CONSTRAINT_FIELDS = {"gender", "male_count", "female_count", "party_size"}
if _CONSTRAINT_FIELDS & set(update_data.keys()):
    # 기존 배정이 새 제약을 위반하는지 체크
    from app.services.room_assignment_invariants import check_assignment_validity
    invalid_dates = check_assignment_validity(db, db_reservation)
    if invalid_dates:
        # 위반 배정만 unassign → 다음 fill 기회에 재배정
        room_assignment.unassign_room(
            db, reservation_id,
            from_date=min(invalid_dates),
            end_date=(max(invalid_dates) + timedelta(days=1)).isoformat(),
        )
        log_activity(..., title=f"제약 위반 배정 해제: {invalid_dates}")
```

**새 함수**: `backend/app/services/room_assignment_invariants.py` (신규)
```python
def check_assignment_validity(db, reservation) -> List[str]:
    """현재 배정이 예약 제약을 만족하는지 체크.

    Returns: 위반된 배정의 날짜 리스트 (빈 리스트면 OK)
    """
    invalid = []
    assignments = db.query(RoomAssignment).filter(
        RoomAssignment.reservation_id == reservation.id
    ).all()
    for ra in assignments:
        room = db.query(Room).get(ra.room_id)
        # 도미토리 성별 잠금 체크
        if room.is_dormitory:
            others = db.query(RoomAssignment).filter(
                RoomAssignment.room_id == room.id,
                RoomAssignment.date == ra.date,
                RoomAssignment.reservation_id != reservation.id,
            ).all()
            if others_gender_conflicts(reservation, others, db):
                invalid.append(ra.date); continue
            # 용량 체크
            if not capacity_ok(ra.date, room, reservation, others):
                invalid.append(ra.date); continue
    return invalid
```

##### 2-5b. 방 설정 변경 (biz_item/priority 등)

**파일**: `backend/app/api/rooms.py:498-540` (update_room)

**검증 반영 (C-C)**: 기존 `response_model=RoomResponse` 변경 필요. 신규 응답 모델 추가.

```python
# rooms.py 상단에 추가
class RoomUpdateResponse(BaseModel):
    room: RoomResponse
    warning: Optional[str] = None
    affected_reservation_ids: List[int] = []

# update_room 엔드포인트 수정
@router.put("/{room_id}", response_model=RoomUpdateResponse)  # ← 변경
async def update_room(...):
    ...
    # biz_item_links나 base_capacity 변경 감지
    _AFFECTS_ASSIGNMENT = {"biz_item_ids", "biz_item_links", "base_capacity", "is_dormitory", "bed_capacity"}
    warning = None
    affected_ids = []
    if _AFFECTS_ASSIGNMENT & set(update_data.keys()):
        today = datetime.now(KST).strftime("%Y-%m-%d")
        affected = db.query(RoomAssignment).filter(
            RoomAssignment.room_id == room_id,
            RoomAssignment.date >= today,
        ).all()
        if affected:
            affected_ids = list({ra.reservation_id for ra in affected})
            warning = f"{len(affected)}건의 미래 배정이 영향받을 수 있습니다. 수동 재배정을 고려하세요."

    return RoomUpdateResponse(
        room=_room_to_response(db_room),
        warning=warning,
        affected_reservation_ids=affected_ids,
    )
```

**프론트 대응** (`RoomSettings.tsx`): 
- `roomsAPI.update()` 응답 파서를 `res.data.room` 으로 접근 변경
- `res.data.warning` 있으면 배너 표시 + "영향 예약 재배정" 버튼

**프론트 대응**: `RoomSettings.tsx`에 경고 배너 + "영향받은 날짜 재배정" 버튼 추가.

##### 2-5c. Naver 동기화 시 invariant 체크 (검증 반영 C-2)

**문제**: 네이버에서 성별/인원 변경이 동기화로 들어와도 `_update_reservation`은 `reconcile_dates`(날짜 변경만 감지)만 호출하고 invariant 체크가 없음. FILL-ONLY 전환 후엔 도미토리 혼성 상태가 방치됨.

**파일**: `backend/app/services/naver_sync.py:443-455` 뒤에 추가

```python
# _update_reservation 끝부분 (line 497 근처)

# ★ 검증 반영 (C-2): 성별/인원/도미토리 플래그 변경 시 invariant 체크
_CONSTRAINT_FIELDS_CHANGED = (
    old_male != existing.male_count or
    old_female != existing.female_count or
    old_party_size != existing.party_size or
    old_gender != existing.gender
)
if _CONSTRAINT_FIELDS_CHANGED:
    from app.services.room_assignment_invariants import check_assignment_validity
    invalid_dates = check_assignment_validity(db, existing)
    if invalid_dates:
        # 위반된 미래 날짜 배정만 해제 (과거는 건드리지 않음)
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        future_invalid = [d for d in invalid_dates if d > today_str]
        if future_invalid:
            room_assignment.unassign_room(
                db, existing.id,
                from_date=min(future_invalid),
                end_date=(datetime.strptime(max(future_invalid), "%Y-%m-%d") 
                          + timedelta(days=1)).strftime("%Y-%m-%d"),
            )
            log_activity(
                db, type="room_move",
                title=f"[{existing.customer_name}] 네이버 동기화 제약 위반 — 배정 해제",
                detail={
                    "reservation_id": existing.id,
                    "invalid_dates": future_invalid,
                    "trigger": "naver_sync_constraint_violation",
                },
                created_by="naver_sync",
            )
```

**효과**: 네이버에서 고객 성별 변경 → 기존 도미토리 배정이 위반 → 자동 해제 → 다음 auto_assign이 적합한 방 재배정.

#### 2-6. once_per_stay 중복 발송 방지 (검증 반영 D6)

**문제**: 연박 그룹 해제(`unlink_from_group`) 후 once_per_stay 스케줄이 중복 발송 가능.

**시나리오**:
```
그룹 G1: [A(4/20~22), B(4/22~24)] 체크인 SMS once_per_stay
  → A에 발송 완료

관리자가 그룹 해제
  → B가 standalone (stay_group_id=None)

다음 schedule 실행:
  B의 stay_group_id=None 분기 → B의 발송 이력만 조회 → 없음 → 발송 🐛
```

**파일**: `backend/app/scheduler/template_scheduler.py:496-504`

**수정**: standalone 분기에서 reservation_id 대신 customer_name+phone 기반 조회
```python
# Before: B의 reservation_id로만 체크
already_sent = query.filter(
    ReservationSmsAssignment.reservation_id == res.id
).scalar()

# After: 같은 사람(이름+전화)의 모든 예약에서 체크
already_sent = self.db.query(sa_exists().where(
    (ReservationSmsAssignment.template_key == schedule.template.template_key) &
    (ReservationSmsAssignment.sent_at.isnot(None)) &
    (ReservationSmsAssignment.reservation_id.in_(
        self.db.query(Reservation.id).filter(
            Reservation.customer_name == res.customer_name,
            Reservation.phone == res.phone,
        )
    ))
)).scalar()
```

**트레이드오프**: 이름+전화가 동일한 "다른 사람"(예: 가족 같은 전화번호) 영향 가능하나, once_per_stay 의도상 허용 가능.

---

##### 2-5 공통: check_assignment_validity 체크 항목 (검증 반영 M-4)

```python
def check_assignment_validity(db, reservation) -> List[str]:
    """배정이 제약 위반하는 날짜 리스트 반환. 호출자는 예외 감싸야 함."""
    invalid = []
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    
    # ★ H-B 최적화: joinedload로 Room 미리 로드 (N+1 방지)
    from sqlalchemy.orm import joinedload
    assignments = db.query(RoomAssignment).options(
        joinedload(RoomAssignment.room)
    ).filter(
        RoomAssignment.reservation_id == reservation.id,
        RoomAssignment.date > today_str,
    ).all()
    
    if not assignments:
        return invalid
    
    # ★ H-B 최적화: 모든 (room_id, date) 쌍에 대한 others를 배치 조회
    lookup_keys = [(ra.room_id, ra.date) for ra in assignments]
    room_ids = list({k[0] for k in lookup_keys})
    dates = list({k[1] for k in lookup_keys})
    all_others = db.query(RoomAssignment).filter(
        RoomAssignment.room_id.in_(room_ids),
        RoomAssignment.date.in_(dates),
        RoomAssignment.reservation_id != reservation.id,
    ).all()
    others_by_key = defaultdict(list)
    for o in all_others:
        others_by_key[(o.room_id, o.date)].append(o)
    
    for ra in assignments:
        room = ra.room  # joinedload 덕분에 추가 쿼리 없음
        if not room: continue
        key = (ra.room_id, ra.date)
        others = others_by_key.get(key, [])
        
        if room.is_dormitory:
            if _has_gender_conflict(db, reservation, ra, room, others):
                invalid.append(ra.date); continue
            if _has_capacity_overflow(reservation, ra, room, others):
                invalid.append(ra.date); continue
        else:
            # 일반실: 미래 날짜 이중배정
            if len(others) > 0:
                invalid.append(ra.date); continue
    return invalid
```

**호출자 try/except 패턴 (M-CATCH)**:
```python
# api/reservations.py:update_reservation 내
try:
    invalid_dates = check_assignment_validity(db, db_reservation)
except Exception as e:
    logger.error(f"check_assignment_validity failed: {e}")
    invalid_dates = []  # 실패 시 체크 스킵 — 예약 수정 자체는 진행

if invalid_dates:
    ...
```

**race condition 대응 (H-G)**: check + unassign 사이에 다른 세션이 개입할 수 있음. 실무적 리스크는 낮으며, 현재는 문서화만 수행. 필요 시 Phase 3에서 `SELECT FOR UPDATE` 강화 검토.

---

### Phase 3 — 정리 & 테스트 보강 (3일)

#### 3-1. denormalized 필드 fallback 제거 [B-6, B-8 해결]

**파일 수정 (검증 반영 H-4: room_password 계열도 포함)**:

1. `templates/variables.py` fallback 제거:
   - line 234: `reservation.room_password` fallback → 빈 문자열
   - line 245: `reservation.room_number` fallback → 빈 문자열
   - line 253-254: room_number 역조회 fallback → 제거

2. `api/reservations.py` API 응답:
   - line 174: `room_number` — date 없을 때도 batch_room_lookup(date=None) 사용
   - line 175: `room_password` — 동일하게 batch_room_lookup 사용

3. `room_assignment.py`:
   - `sync_denormalized_field()` (line 398-429) deprecated, 호출부 제거
   - `clear_all_for_reservation()`의 `reservation.room_number/password = None` 은 유지 (cleanup 목적)

4. `naver_sync.py:475-476` (당일 취소):
   - `existing.room_number = None / room_password = None` 명시적 cleanup 유지
   - 주석 추가: "cleanup only — denormalized field 읽기는 deprecated"

5. 테스트 업데이트 (검증 반영):
   - `test_assign_room.py:97`: `assert res.room_number == "A101"` → RoomAssignment 기반 assertion으로 변경
   - `test_sms_sender.py` 등 room_password fallback 테스트도 점검

**필드 DEPRECATE**:
- `models.py:101-102` `room_number`/`room_password` 주석에 "DEPRECATED: use RoomAssignment (read via room_lookup)" 추가
- 실제 컬럼 DROP은 **하지 않음** (네이버 동기화 cleanup + alembic 003 마이그레이션 호환)

#### 3-1b. 빈 방 정보 SMS 발송 차단 (검증 반영 D3)

**문제**: Phase 3-1로 denormalized fallback 제거 후, 미배정 예약이 칩을 가지면 `{{room_num}}` → `""` 로 치환되어 "방 정보 비어있는 SMS"가 발송될 수 있음. `find_unreplaced_vars`는 빈 문자열을 정상 치환으로 간주해서 차단 못함.

**파일**: `backend/app/services/sms_sender.py:send_single_sms`

**수정**:
```python
# 변수 치환 직후, 실제 발송 직전에 추가
_ROOM_VARS_REQUIRED = ("{{room_num}}", "{{building}}", "{{room_password}}")
if any(v in template_content for v in _ROOM_VARS_REQUIRED):
    if not variables.get("room_num") or not variables.get("building"):
        logger.error(
            f"Blocking SMS: room info empty but template requires it. "
            f"res={reservation.id} template={template_key}"
        )
        # 실패로 기록
        from app.services.sms_tracking import record_sms_failed
        record_sms_failed(
            db, reservation.id, template_key,
            error="방 정보 누락 (미배정 상태)",
            date=date or "",
        )
        return {"success": False, "error": "방 정보 누락 (미배정 상태)"}
```

**효과**: 미배정 예약에 객실안내 템플릿이 실수로 발송되는 경우 차단.

---

#### 3-2. 테스트 추가 [B-7 해결]

**신규 테스트**:
```
tests/integration/
├── test_reconcile_dates.py       — 연장 케이스 3개 추가
├── test_naver_sync_extend.py     — NEW (네이버 date 변경 시나리오)
├── test_extend_stay_api.py       — NEW (assigned_by 검증)
├── test_auto_assign_failure.py   — NEW (배정 실패 로깅 검증)
└── test_invariants.py            — NEW (INV-1~4 전반 검증)
```

**INV 검증 테스트 예시**:
```python
def test_invariant_roomassignment_coverage(db):
    """모든 CONFIRMED 예약의 RoomAssignment 개수가 체류일수와 일치."""
    for res in all_confirmed_with_room():
        expected = len(date_range(res.check_in_date, res.check_out_date))
        actual = db.query(RoomAssignment).filter(
            RoomAssignment.reservation_id == res.id
        ).count()
        assert actual == expected, f"res={res.id}: expected {expected}, got {actual}"
```

---

## 3. 수정 영향 범위 매트릭스

| 파일 | Phase 0 | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|---|
| `db/models.py` | **CampaignLog/Rule/Document/GenderStat 클래스 삭제 + TENANT_MODELS 등록 해제 + Tenant.snapshot_refresh_times 제거** | — | — | deprecated 주석 (room_number/password) |
| `db/database.py` | snapshot_refresh_times runtime migration 제거 | — | — | — |
| `services/room_assignment.py` | — | `reconcile_dates()` 확장 (FOR UPDATE 포함) + 이중배정 밀어내기 + 도미토리 강경책 (savepoint + batch) | — | `sync_denormalized_field()` deprecated |
| `services/room_auto_assign.py` | — | — | 실패 수집/로깅 + **FILL-ONLY 전환** | — |
| `services/naver_sync.py` | — | Phase 5 트리거 + 당일 취소 surcharge 정리 | 2-5c invariant 체크 | — |
| `services/schedule_utils.py` | — | — | docstring | — |
| `services/chip_reconciler.py` | — | — | — | — |
| `services/sms_sender.py` | — | — | — | 빈 room_num SMS 차단 (3-1b) |
| `services/room_assignment_invariants.py` | — | — | **NEW** (joinedload + batch) | — |
| `services/diag_logger.py` | **NEW** (TimedRotating + tenant_id 자동) | — | — | — |
| `api/reservations.py` | — | extend_stay 수정 + "오늘 이후" 보정 + 과거 가드 + 직접 SQL → clear_all 교체 | 제약 위반 감지 | denormalized fallback 제거 |
| `api/rooms.py` | — | — | `RoomUpdateResponse` 신규 + 설정 변경 경고 | — |
| `scheduler/template_scheduler.py` | — | — | once_per_stay 중복 방지 (D6) | — |
| `alembic/versions/` | **NEW: DROP 4테이블 + snapshot_refresh_times 컬럼** | NEW: assigned_by 정리 마이그레이션 | — | — |
| `tests/` | models 테스트 정리 | reconcile_dates + 이중배정 + 도미토리 | auto_assign 실패 + daily fill-only | invariants + 전수 |
| `RoomAssignment.tsx` | — | 과거 드롭 차단 + 모달 라벨 변경 + SSE handler 추가 | — | — |
| `RoomSettings.tsx` | — | — | 경고 배너 UI + RoomUpdateResponse 파싱 | — |
| `ActivityLogs.tsx` | — | — | room_assign_failed 타입 렌더링 | — |
| `docker-compose.prod.yml` | TZ=Asia/Seoul + logs 볼륨 마운트 | — | — | — |

**DB 스키마 변경**:
- Phase 0: **DROP** 4개 테이블 (CampaignLog, Rule, Document, GenderStat) + 1개 컬럼 (Tenant.snapshot_refresh_times)
- Phase 1: 데이터 마이그레이션 1개 (`assigned_by` 정리) — 컬럼 변경 없음
- Phase 2/3: 컬럼 변경 없음 (Reservation.room_number/password 컬럼은 유지, 읽기만 제거)

**~~facade 도입 폐기~~**: `room_assignment_service.py` 신규 파일은 만들지 않음. 대신 Phase 2-3에서 직접 SQL 2곳만 `clear_all_for_reservation` 호출로 교체.

---

## 4. 위험 & 롤백

### 4-1. 위험 요소
| 위험 | 완화 방안 |
|---|---|
| **Phase 0**: 잔재 테이블 DROP이 숨겨진 의존성 깨뜨림 | 배포 전 grep 재확인 + 별도 배포로 분리 (Phase 0 → 안정 확인 → Phase 1) |
| `reconcile_dates` 확장이 기존 동작 깨뜨림 | 기존 3개 테스트 통과 확인 후 신규 케이스 추가 |
| `naver_sync` Phase 5 확장으로 auto-assign 과다 실행 | `dates` 셋에 `d >= today` 필터 유지, 로그 모니터링 |
| `assigned_by` 값 변경이 기존 쿼리에 영향 | `assigned_by NOT IN ('auto','manual')` 데이터 수 사전 쿼리 |
| denormalized 필드 제거가 외부 integration 깨뜨림 | 필드 DROP 안 하고 주석만. 읽기 fallback만 제거 |
| FILL-ONLY 즉시 전환으로 엣지 케이스 놓침 | Phase 2-5 invariant 체크가 엣지 커버 + 7일 집중 감시로 검증 |
| 동시성 race condition (reconcile_dates + assign_room 동시) | FOR UPDATE 락 추가 (C-A/H-C) |
| Push-out 부분 실패 세션 오염 | savepoint로 각 iteration 격리 (C-D) |
| 자정 경계에서 `today_str` 불일치 | 요청 진입점에서 1회 계산, 파라미터 전달 (H-A) |

### 4-2. 롤백 전략

**옵션 B 일괄 배포이므로 롤백 단위는 "전체"**:

```
상황 감지:
  - refactor-diag.log에서 CRITICAL 이벤트
  - unique constraint 위반
  - 이상 패턴 (예: dormitory.hardline 폭주)

롤백 결정:
  - 부분 핫픽스 가능: 해당 작업만 revert (커밋 단위로 분리)
  - 전체 롤백 필요: Phase 1~3 모든 커밋 revert
  
롤백 실행:
  git revert <커밋들>
  docker compose restart backend
  (DB 스키마 변경 없어서 깔끔)

부작용 정리:
  - assigned_by 마이그레이션은 이미 적용 상태 → 롤백 불필요
  - refactor-diag.log는 그대로 유지 → 사후 분석
```

**안전장치**:
- 각 작업을 **독립 커밋**으로 유지 (그룹 커밋 금지)
- PR 단위는 Phase 기준 (1, 2, 3) — 리뷰 시 맥락 이해 용이
- 진단 로깅이 "어디서 문제 생겼는지" 빠르게 식별해 줌

---

## 5. 일정 & 작업 순서

```
┌─────────────────────────────────────────────────────────────┐
│ 옵션 B (일괄 구현 + 집중 로깅 + 7일 감시)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Day -1  │ 사전 조사                                           │
│         │  - 운영 DB `assigned_by` 분포 쿼리                    │
│         │  - 잔재 테이블 grep 최종 확인                         │
│         │                                                   │
│ Day 0   │ 공통 준비 + Phase 0                                  │
│         │  - diag_logger.py 작성                              │
│         │  - docker-compose TZ + 볼륨 마운트 추가                │
│         │  - Phase 0: 잔재 4테이블 + 1컬럼 DROP 마이그레이션     │
│         │                                                   │
│ Day 1-2 │ Phase 1 핵심 버그                                    │
│         │  - 1-1. reconcile_dates (FOR UPDATE + 복사) [B-1,X3]│
│         │  - 1-2. naver_sync Phase 5 트리거 [B-2]             │
│         │  - 1-3. extend_stay assigned_by [B-3]              │
│         │  - Q2 마이그레이션 (assigned_by 정리)                  │
│         │                                                   │
│ Day 3-5 │ Phase 1 충돌 정책 + Critical 수정                     │
│         │  - 1-4. 이중배정 밀어내기 + savepoint [CRIT-1,C-D]   │
│         │  - 1-5. 도미토리 강경책 + batch + savepoint [C-B,C-D]│
│         │  - 1-6. "오늘 이후" + 과거 차단 [UX-1]               │
│         │  - H-E/H-F: warnings 반환 + 즉시 재배정 트리거         │
│         │                                                   │
│ Day 6-8 │ Phase 2 가시성/일관성                                 │
│         │  - 2-1. 배정 실패 + SSE + ActivityLogs.tsx [B-4,H-D]│
│         │  - 2-2. date_range docstring [B-5]                 │
│         │  - 2-3. 직접 SQL → clear_all + naver 취소 [M-3,S5]  │
│         │  - 2-4. FILL-ONLY 즉시 전환 [B-9]                    │
│         │  - 2-5. invariants (joinedload + try/except) [H-B] │
│         │  - 2-5c. naver_sync invariant 체크 [C-2]            │
│         │  - 2-6. once_per_stay 중복 방지 [D6]                │
│         │                                                   │
│ Day 9-10│ Phase 3 정리                                        │
│         │  - 3-1. denormalized fallback 제거 [B-6,B-8,H-4]    │
│         │  - 3-1b. 빈 room_num SMS 차단 [D3]                  │
│         │  - 3-2. 테스트 보강 [B-7]                            │
│         │                                                   │
│ Day 11  │ 통합 테스트 + 스테이징 배포                            │
│         │  - 전체 테스트 스위트 통과                           │
│         │  - 진단 로그 정상 기록 확인                           │
│         │                                                   │
│ Day 12  │ 운영 배포 🚀                                          │
│         │                                                   │
│ Day 13-19 │ 7일 집중 감시 📡 (매일 저와 세션)                    │
│         │  - refactor-diag.log.YYYY-MM-DD 분석                │
│         │  - FILL-ONLY 안정성 관찰                              │
│         │  - 이상 패턴 발견 시 핫픽스                            │
│         │                                                   │
│ Day 20  │ Cleanup                                             │
│         │  - 진단 로그 비활성화 (DIAG_LOGGING=false)             │
│         │  - 안정 확인 후 소스코드 완전 제거 (cleanup PR)        │
│         │                                                   │
└─────────────────────────────────────────────────────────────┘

총 ~3.5주 (준비 1일 + 구현 11일 + 감시 7일 + 정리 1일)
```

### 5-1. Day 별 진단 로깅 작업 포함 내용

각 Phase 작업에 `diag(...)` 호출을 함께 넣는 원칙:

| Phase 작업 | 필수 diag 이벤트 |
|---|---|
| Phase 0 DROP | `phase0.drop_table` (각 테이블 제거 시) |
| 1-1 reconcile_dates | `reconcile_dates.enter/exit`, `reconcile_dates.extension_pushed_out` (X3) |
| 1-2 naver_sync Phase 5 | `naver_sync.phase5` (added_count + date_changed_ids) |
| 1-3 extend_stay | `extend_stay.assign` (assigned_by 값 검증) |
| 1-4 이중배정 | `double_booking.pushed_out` (pushed_res_id, cause, date) |
| 1-5 도미토리 | `dormitory.hardline` (pushed_count, reason) |
| 1-6 과거 차단 | `past_drop.blocked` (프론트 + 백엔드 양쪽) |
| 2-1 실패 로깅 | `auto_assign.failed` (reason 분류 포함) |
| 2-3 naver 당일 취소 | `naver_sync.same_day_cancel` (S5) |
| 2-4 FILL-ONLY | `daily_assign.mode` (처리 건수, skipped 건수) |
| 2-5 invariant 체크 | `invariant.violation_detected` (reservation_id, invalid_dates) |
| 2-5c naver invariant | `naver_sync.constraint_violation` |
| 2-6 once_per_stay | `once_per_stay.dedup_hit` (중복 방지된 reservation) |
| 3-1b 빈 room 차단 | `sms_sender.blocked_empty_room` |
| Q2 마이그레이션 | `assigned_by.cleanup` (영향 레코드 수) |
| Push-out 재배정 | `pushed_out.reassign_triggered` (H-F) |

---

## 6. 성공 기준

Phase 0 완료 시:
- `grep -rn "CampaignLog\|GenderStat\|Document\b\|Rule\b\|snapshot_refresh_times"` 결과 models.py 외 0건
- DB에 해당 테이블 존재하지 않음
- diag_logger가 `backend/logs/refactor-diag.log` 에 정상 기록

Phase 1 완료 시:
- 3박 예약을 4박으로 연장 시, 4박째 미배정 안 됨 (B-1)
- 네이버에서 check_out 연장된 예약이 다음 정기 sync에서 auto-assign됨 (B-2)
- `SELECT DISTINCT assigned_by FROM room_assignments` → `{'auto', 'manual'}`만 (B-3, Q2)
- 연박자 이동 시 미래 날짜에 다른 예약자 있으면 자동으로 미배정 밀어내기 (CRIT-1, X3)
- 도미토리 수동 배정 시 혼성/용량 위반 시 기존 멤버 전부 미배정 (CRIT-2)
- 과거 날짜로 드롭 시 프론트 + 백엔드 양쪽에서 차단 (UX-1, M-1)
- 동시 이중배정 재현 불가 (FOR UPDATE 락 — C-A/H-C)
- Push-out 부분 실패해도 성공한 밀어내기는 유지 (savepoint — C-D)
- 사용자가 밀어내기 경고를 toast로 확인 (H-E)
- 밀려난 예약이 즉시 재배정 시도됨 (H-F)

Phase 2 완료 시:
- ActivityLog에 `room_assign_failed` 타입 레코드 생성 + ActivityLogs.tsx에 표시 (B-4, H-D)
- 운영자가 실시간 토스트로 배정 실패 인지 (Q3)
- `daily_assign_rooms`가 FILL-ONLY 모드로 안정 운영 (7일 관찰 후)
- 성별/인원 변경 시 제약 위반 배정 자동 해제 (2-5a)
- 네이버 동기화에서 성별 변경 시 invariant 체크됨 (C-2, 2-5c)
- 방 설정 변경 시 `RoomUpdateResponse`로 경고 배너 표시 (C-C)
- once_per_stay 그룹 해제 후 중복 발송 없음 (D6)

Phase 3 완료 시:
- `reservation.room_number` / `reservation.room_password` 읽는 코드 경로 0건 (grep 기준, 테스트 제외)
- 미배정 예약에 객실안내 SMS 발송 시도 시 차단됨 (D3)
- invariants 전수 테스트 통과

배포 후 7일 감시 완료 시:
- `[CRITICAL]` 이벤트 0건
- unique constraint 위반 0건
- 배정 실패 건수가 기준선 이하
- 진단 로그 일일 리포트 정상 생성
- FILL-ONLY 모드에서 이상 증상 없음 → Cleanup 진행

---

## 7. 검토 포인트 (사용자 확인 요청)

### 7-1. 확정된 결정 (모두 확정)

| # | 결정 | 선택 |
|---|---|---|
| 제안 1 | 미래 이중배정 밀어내기 | 채택 → Phase 1-4 |
| 제안 2 | "오늘 이후" + 과거 차단 | 채택 → Phase 1-6 |
| 제안 3a | 도미토리 강경책 | 채택 → Phase 1-5 |
| HIGH-3/5, MED-6 | 불필요로 판정 (0-3 참조) | — |
| **Q1** | Phase 2-3 서비스 facade | ~~A (필수)~~ → **B (타겟 수정)** (검증 후 변경) |
| **Q2** | `assigned_by` 기존 데이터 정리 | **A (SQL 정리 + ActivityLog 보존)** |
| **Q3** | 배정 실패 알림 | **B (ActivityLog + SSE 토스트)** |
| **Q4** | denormalized 필드 | 컬럼 유지, 읽기 fallback만 제거 |
| **Q5** | 작업 진행 방식 | **B (일괄) + 집중 로깅** |
| **Q5-α** | 매일 감시 방식 | **γ (저와 매일 세션)** |
| **Q5-β** | FILL-ONLY 전환 | **X (즉시 conservative)** |
| **Q5-γ** | 로그 저장 위치 | **별도 파일 + 7일 TimedRotating** |
| **Q6** | FILL-ONLY 전환 방식 | 즉시 conservative (로그로 감시) |
| **Q7-1** | `check_assignment_validity` 위치 | **A (신규 파일 `room_assignment_invariants.py`)** |
| **Q7-2** | 방 설정 변경 시 자동화 | **X (경고만 + 수동 재배정 버튼)** |

### 7-2. 진단 로깅 전략 (Q5 결정 반영)

**목적**: 일괄 배포 후 7일 집중 감시를 위한 전용 로그 시스템.

**구조**:
```python
# backend/app/diag_logger.py (신규)
import logging, os
from logging.handlers import TimedRotatingFileHandler

_DIAG_ENABLED = os.environ.get("DIAG_LOGGING", "true").lower() == "true"

_logger = None

def get_diag_logger():
    global _logger
    if _logger: return _logger

    _logger = logging.getLogger("refactor_diag")

    if not _DIAG_ENABLED:
        # OFF 모드: 아무것도 기록 안 함
        _logger.addHandler(logging.NullHandler())
        _logger.setLevel(logging.CRITICAL + 1)
        _logger.propagate = False
        return _logger

    log_dir = os.environ.get("DIAG_LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    handler = TimedRotatingFileHandler(
        f"{log_dir}/refactor-diag.log",
        when="midnight",
        backupCount=7,  # 7일치만 보관, 그 이전 자동 삭제
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    return _logger


def diag(event: str, **kwargs):
    """모든 진단 로그는 이 함수만 사용. Cleanup 시 grep 대상."""
    if not _DIAG_ENABLED:  # M-TID 최적화: 조기 return으로 format 비용 제거
        return
    logger = get_diag_logger()
    # M-TID: tenant_id 자동 포함 (테넌트별 로그 필터링 가능하게)
    from app.db.tenant_context import current_tenant_id
    kwargs.setdefault("tid", current_tenant_id.get())
    kv = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"[{event}] {kv}")
```

**M-TZ 주의**: `TimedRotatingFileHandler(when="midnight")` 는 **시스템 local time** 기준. Docker 컨테이너 기본 TZ는 UTC이므로 `docker-compose.prod.yml`에 `TZ=Asia/Seoul` 환경변수 반드시 설정해야 KST 자정 기준 로그 분리됨.

**사용 예시**:
```python
from app.diag_logger import diag

def reconcile_dates(db, reservation):
    diag("reconcile_dates.enter",
         res_id=reservation.id,
         check_in=reservation.check_in_date,
         check_out=reservation.check_out_date)
    # ... 기존 로직 ...
    diag("reconcile_dates.exit",
         res_id=reservation.id,
         deleted=deleted_count,
         inserted=inserted_count)
```

**감시 대상 이벤트 (10개)**:

| Event | 기록 시점 | 기록 내용 |
|---|---|---|
| `reconcile_dates.enter/exit` | reconcile_dates 호출 | res_id, valid/deleted/inserted dates |
| `naver_sync.phase5` | Phase 5 트리거 | added_count, date_changed_ids, dates |
| `extend_stay.assign` | extend_stay assign_room | new_res_id, assigned_by (값 검증) |
| `double_booking.pushed_out` | 미래 이중배정 밀어내기 | pushed_res_id, caused_by, date |
| `dormitory.hardline` | 도미토리 강경책 발동 | room_id, date, reason, pushed_count |
| `past_drop.blocked` | 과거 드롭 차단 | res_id, target_date |
| `auto_assign.failed` | auto_assign silent continue | res_id, reason, target_date |
| `daily_assign.mode` | FILL-ONLY 분기 | mode, processed_count |
| `clear_all.direct_sql_replaced` | 직접 SQL → clear_all 교체 경로 | caller, reservation_id |
| `reconcile_dates.extension_pushed_out` | X3 연장 시 밀어내기 | pushed_res_id, caused_by |
| `invariant.violation_detected` | Phase 2-5 체크 위반 발견 | reservation_id, invalid_dates |
| `once_per_stay.dedup_hit` | 그룹 해제 후 중복 방지됨 | reservation_id, template_key |
| `sms_sender.blocked_empty_room` | 빈 room_num SMS 차단 (D3) | reservation_id, template_key |
| `pushed_out.reassign_triggered` | 밀어내기 후 즉시 재배정 (H-F) | affected_dates |
| `phase0.drop_table` | Phase 0 테이블 제거 | table_name, row_count |
| `assigned_by.cleanup` | 마이그레이션 | original_value, count |

**파일 구조**:
```
backend/logs/
├── refactor-diag.log              ← 오늘
├── refactor-diag.log.2026-04-26   ← 1일 전
├── ...
└── refactor-diag.log.2026-04-20   ← 6일 전 (7일 전부터 자동 삭제)
```

**Docker 볼륨 마운트 + TZ 설정 필요** (M-TZ):
```yaml
# docker-compose.prod.yml
services:
  backend:
    volumes:
      - ./backend/logs:/app/logs
    environment:
      - TZ=Asia/Seoul            # ★ 필수 — 자정 기준 로그 분리용
      - DIAG_LOGGING=true
      - DIAG_LOG_DIR=/app/logs
```

### 7-3. Cleanup 절차 (7일 관찰 완료 후)

**Step 1: 환경변수로 즉시 비활성화**
```bash
# .env 수정
DIAG_LOGGING=false

# 서버 재시작
```
→ 모든 `diag(...)` 호출이 no-op. 코드는 그대로 두고 기능만 OFF.

**Step 2: 소스코드 완전 제거 (확신 시)**
```bash
# 1. 호출 지점 확인
grep -rn "diag(" backend/app/ | grep -v "import" | grep -v "def diag"

# 2. 자동 제거
sed -i '/^\s*diag(/d' backend/app/**/*.py
sed -i '/from app.diag_logger import diag/d' backend/app/**/*.py

# 3. diag_logger.py 삭제
rm backend/app/diag_logger.py

# 4. 로그 파일 정리
rm -rf backend/logs/refactor-diag.log*

# 5. 단일 커밋
git add -A && git commit -m "Remove refactor-2026-04 diagnostic logging"
```

---

검토 후 수정사항이나 질문 주세요. 확정되면 Phase 1-1부터 착수하겠습니다.
