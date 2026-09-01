# 트윈 3인실 우선배정 설계 (best-fit by grade)

> 상태: **설계 완료 / 구현 전 / 안전감사 대기**. 대상 테넌트: **STABLE(tid=2)만**.
> 작성: 2026-07-01. 관련: [twin-capacity-assign-analysis 워크플로우 분석 결과], `services/room_auto_assign.py::_sort_candidate_rooms`.

## 1. 목적

트윈룸 상품(1~2인 기준)에 **3인**으로 들어온 예약을 **3인실 트윈(트윈3인실)** 에 우선 배정하고,
**2인** 예약은 3인실 트윈을 **가장 나중에** 배정(3인 예약을 위해 아껴둠)한다.

- 지금: 트윈룸 후보를 gender priority + sort_order 순으로만 배정 → 3인 예약이 priority 낮은 **2인 트윈**에 먼저 잡힘(예: A302 pri=0).
- 목표: 인원수(party_size)에 따라 **용량 적합도(best-fit)** 를 1순위로, 기존 priority는 그 안에서 유지.

## 2. 데이터 근거 (실 DB, STABLE tid=2)

- biz `4779014` '[특가] 오션뷰 트윈룸' → **grade=3(2인) 10개 + grade=4(3인실) 4개 혼재** (같은 상품). 3인 예약 후보에 3인실 방이 포함됨 → **정렬만으로 해결 가능**.
  - grade=4(3인실): B207, A205, A206, A308.
- biz `4779030` '오션뷰 스파 트윈룸' → grade=3 3개(3인실 없음). 별도 상품, 영향 없음(균일 grade).
- **grade 가 유일 신호**: `max_capacity` 전부 4(기본값·미사용), `base_capacity` 전부 2(추가요금과 결합돼 재활용 위험). grade registry: `4=트윈3인실 < 5=스위트`(둘 다 3인+ 수용).
- **priority 는 방마다 전부 다른 값(0~16)** → 용량 항목을 뒤 tiebreaker로 넣으면 효과 0 → **용량 항목이 priority보다 앞서야 함**.
- **party_size 신뢰도(biz 4779014, 확정 618건)**: `party_size>=3` 85건 == `(male+female)>=3` 85건(정확히 일치). `party_size=0/null` 4건(모두 m+f=0=진짜 1인/미상, 숨은 3인 아님). → **STABLE 에선 party_size 신뢰 가능, 선결 A(인원수 교정) 불필요**. 그래도 정렬용 headcount 는 안전하게 3단 폴백 사용.

## 3. 변경 (라인 단위 before/after) — `services/room_auto_assign.py`

### 3-1. `_sort_candidate_rooms` (253-264): capacity-fit tier 를 1순위로 prepend

**Before**
```python
def _sort_candidate_rooms(rooms: List[Room], biz_item_id: str, gender: str) -> List[Room]:
    """Sort candidate rooms by gender-specific priority from RoomBizItemLink."""
    def get_priority(room: Room) -> tuple:
        for link in room.biz_item_links:
            if link.biz_item_id == biz_item_id:
                if gender == "여":
                    return (link.female_priority or 0, room.sort_order, room.id)
                elif gender == "남":
                    return (link.male_priority or 0, room.sort_order, room.id)
                break
        return (0, room.sort_order, room.id)
    return sorted(rooms, key=get_priority)
```

**After**
```python
def _sort_candidate_rooms(rooms: List[Room], biz_item_id: str, gender: str,
                          people_count: int = 1) -> List[Room]:
    """Sort candidate rooms by capacity-fit tier, then gender-specific priority.

    capacity-fit: 3인 이상 예약은 트윈 3인실(grade==4) 우선, 2인 이하는 3인실을
    최후로 아껴둠(3인 예약용). tier 결정 후 같은 tier 안에서는 기존
    (gender priority → sort_order → id) 순서를 그대로 유지한다.
    grade 가 균일한 후보군(도미/더블/스파트윈/스위트/HANDAM=NULL 등)에서는
    cap_rank 가 모두 같아 no-op. 임계값 3 = 표준 트윈/더블 base(2) 초과 기준.
    grade==4 는 STABLE 에서 트윈3인실 전용(스위트=grade5 는 제외, 자기 pool 고립이라 무관).
    None==4 → False 라 grade 미설정 방은 안전하게 non-3인실 취급.
    """
    needs_extra = people_count >= 3
    def get_priority(room: Room) -> tuple:
        three_capable = (room.grade == 4)   # 트윈 3인실 전용 (스위트 grade5 제외)
        if needs_extra:
            cap_rank = 0 if three_capable else 1   # 3인+: 3인실 먼저
        else:
            cap_rank = 1 if three_capable else 0   # 2인-: 3인실 최후
        for link in room.biz_item_links:
            if link.biz_item_id == biz_item_id:
                if gender == "여":
                    return (cap_rank, link.female_priority or 0, room.sort_order, room.id)
                elif gender == "남":
                    return (cap_rank, link.male_priority or 0, room.sort_order, room.id)
                break
        return (cap_rank, 0, room.sort_order, room.id)
    return sorted(rooms, key=get_priority)
```

> priority 로직(남/여 분기, break→fallthrough, `or 0`)은 **완전히 동일**. cap_rank 만 튜플 맨 앞에 추가.

### 3-2. 호출부 (356-360): 정렬용 headcount 계산 후 전달

**Before**
```python
        res_gender = single_gender(res)
        candidate_rooms = _sort_candidate_rooms(candidate_rooms, res.naver_biz_item_id, res_gender)
```

**After**
```python
        res_gender = single_gender(res)
        # 정렬용 headcount = surcharge.compute_guest_count 와 동일(party_size → male+female → 1).
        # booking_count(=방 개수) 폴백은 '3방 예약'을 '3인'으로 오판할 수 있어 제외(안전감사).
        # 도미토리 용량체크용 people_count(아래 382줄)는 blast radius 최소화 위해 무변경.
        sort_headcount = (res.party_size
                          or ((res.male_count or 0) + (res.female_count or 0))
                          or 1)
        candidate_rooms = _sort_candidate_rooms(
            candidate_rooms, res.naver_biz_item_id, res_gender, people_count=sort_headcount)
```

### 3-3. **미변경** — line 382 `people_count = res.party_size or res.booking_count or 1`
도미토리 용량체크에 쓰이는 이 값은 그대로 둔다(도미토리 동작 회귀 방지).

## 4. 동작 동등성 / no-op 경계

- grade 가 **균일한** 후보군(도미토리 grade=1, 더블 grade=2, 스파트윈 grade=3, HANDAM 전부 NULL)에서는 모든 방의 cap_rank 가 동일 → 정렬 결과 **기존과 동일(no-op)**.
- grade **혼재** 후보군(=STABLE biz 4779014: grade3+4)에서만 재정렬 발생. 이게 정확히 목표 케이스.
- `_sort_candidate_rooms` 호출부는 코드베이스 전체에서 **1곳**(360줄). 다른 소비자 없음.
- 연박/연장 same-room preference(368-371줄)는 정렬 **뒤** 실행 → 기존처럼 우선. 즉 cap_rank 는 **첫박(신규 배정)에만** 적용, 진행중 stay 는 방 유지(의도).

## 5. 시나리오 비교

| # | 상황 | Before | After |
|---|------|--------|-------|
| 1 | 3인, 3인실 여유 | priority 낮은 2인 트윈(A302)에 배정 | **3인실(A205 등) 우선 배정** ✅ |
| 2 | 3인, 3인실 만실 | 아무 빈 트윈 | grade4 rank0 만실→continue→**빈 2인 트윈 overflow**(=기존과 동일, 실패 아님) |
| 3 | 2인, 2인 트윈 여유 | priority상 3인실 먼저 잡힐 수 있음 | **2인 트윈 우선, 3인실 아껴둠** ✅ |
| 4 | 2인, 2인 트윈 만실 | 3인실 배정 | **여전히 3인실 배정**(deprioritize≠forbid) ✅ |
| 5 | 연박 3인(전날 2인 트윈) | 같은 방 유지 | **같은 방 유지**(continuity가 정렬 override) |
| 6 | party_size=0(m+f=0) | 1인 취급 | headcount=1→2인 tier→2인 트윈 우선(정상) |
| 7 | 도미/더블/스파트윈 예약 | 기존 순서 | **동일(no-op)** |

## 6. 부수효과 (재확인)

- **무료 업그레이드 SMS**: 2인을 3인실에서 밀어냄 → grade4에 우연히 떨어지던 오배정 업그레이드 SMS **감소**(positive). 2인이 grade4 강제배정(2인방 만실)되면 여전히 SMS 발화(=오늘과 동일, 실제 업그레이드라 정당).
- **3인의 grade4 배정은 업그레이드 아님**: decide_upgrade_eligible 은 "인원 미초과(guest<=상품 base=2)" 요구 → 3인은 초과라 제외 → 스팸 SMS 없음. ✅
- **추가요금**: 상품 default_capacity 기준(물리방 무관) → 변화 없음. ✅
- **성별락**: 트윈=개인실(non-dorm) → 무관.

## 7. 리스크 / 스코프

- **저위험**: 백엔드 1파일, 정렬 1함수, no-op 경계 명확, 수동배정/도미토리 무관.
- **신호 = `grade == 4` (트윈3인실 전용)**. 실 DB 확인: STABLE grade=4 는 트윈룸 4개(A205/A206/A308/B207)뿐, 다른 타입 없음. 스위트(grade5)는 제외 — 자기 상품(biz 4779035)에 grade5만 있어 고립 pool(무관).
- **grade 혼재 pool 은 트윈(biz 4779014: grade 3+4) 단 하나** 로 실측 확인됨 → 재정렬은 여기서만. 다른 STABLE biz_item 은 grade-4 방 없음 → no-op.
- HANDAM(tid=1)은 grade=NULL이라 `grade==4` False → 자동 no-op → 이번 배포로 영향 없음(백필+검증은 별도).

## 8. 검증 계획

- 인메모리 SQLite 로 `_sort_candidate_rooms` 단위 실증: 시나리오 1~7 정렬 결과 assert.
- 안전감사(blast-radius): `_sort_candidate_rooms` 소비자·grade 혼재 biz_item·연박 override·업그레이드/추가요금 영향.
- 배포 후: STABLE 3인 트윈 예약이 grade4에 배정되는지 activity_log/RoomAssignment 확인.

## 9. 안전감사 결과 (2026-07-01, 4-agent adversarial)

BLOCKER 0 / 크래시·데이터손상 0. 적용 및 수용 판정:

- **[FIX 적용]** `sort_headcount` 에서 `or res.booking_count` 제거 → `party_size or (male+female) or 1` (compute_guest_count 동일). booking_count(방 개수)를 3인으로 오판하는 리스크 제거. (에이전트 3곳 지적)
- **[수용] dorm+grade4 혼재 pool**: 외부 루프가 첫 원소 타입으로 dorm/regular 분기하는 선재(pre-existing) fragility. grade4 는 non-dorm biz(4779014) 전용이라 오늘 무해. 미래 데이터 이상 시에만 잠재 위험.
- **[수용] headcount 이원화**: sort_headcount(male+female 포함) vs line382 people_count(booking_count). 후자는 도미토리 용량체크용이라 blast radius 회피 위해 무변경. regular 방은 용량 하드코딩=1 이라 오버부킹 불가.
- **[수용] naver_split floor-division**: 다객실 분할 시 party_size 근사(나머지를 primary 로)로 grade 유도가 어긋날 수 있음. 실 DB: STABLE 트윈 3인+ 이면서 split = **0건**. booking_count>1 = 1건. 무해한 미래 엣지(최적화만 놓침).
- **[수용] building-scoped SMS**: STABLE active 스케줄 #9~12 가 buildings 필터 사용. 그러나 building-SMS 는 항상 *실제 배정 건물*에 매칭 → 3인이 A동으로 더 몰려도 각자 자기 건물 SMS 를 정확히 수신. 오발송/누락 없음, 분포만 이동(의도).
- **[수용] 테넌트 가드 없음**: `grade==4` 는 전역 신호라 grade4 를 설정한 어떤 테넌트에서도 동작. HANDAM 은 grade=NULL 이라 현재 no-op. 이는 '최종적으로 원하는 동작'(grade 설정=기능 활성)이라 하드코딩 가드 미도입.
- **[확인] 테스트/기타**: 기존 test 픽스처는 grade 미설정 → cap_rank 균일 → 정렬 불변(회귀 없음). party/unstable/activity 섹션은 배정 후보에서 제외되어 무관. `_sort_candidate_rooms` 호출부 1곳뿐.
