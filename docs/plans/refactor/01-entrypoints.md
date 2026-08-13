# S1 — 진입점 전수조사

> 작성 2026-08-06 · 방법: [`00-method.md`](./00-method.md) L1
> 추출 방식: AST 기계 추출 (라우터 데코레이터 · `add_job` · `event.listens_for`) — **누락 없음이 보장됨**

## 요약

| 종류 | 개수 | 비고 |
|------|-----:|------|
| HTTP 엔드포인트 | **104** | 26개 파일 |
| 스케줄러 고정 잡 | **12** | `scheduler/jobs.py` 하드코딩 |
| 스케줄러 동적 잡 | N | `TemplateSchedule` DB 레코드마다 1개 (`schedule_manager`) |
| DB 전역 이벤트 | **2** | 유일한 **강제 관문** |
| SSE 스트림 | 1 | `/api/events/stream` |
| 앱 라이프사이클 | 2 | startup / shutdown |
| HTTP 미들웨어 | 4 | CORS · SecurityHeaders · SlowAPI · diag correlation |

---

## 0. 권한 체계 — ⚠️ CLAUDE.md 와 불일치

실측 `UserRole`: **4종** (CLAUDE.md 는 3종으로 기재 — `CLEANCREW` 누락)

```
SUPERADMIN  →  ADMIN  →  STAFF  →  CLEANCREW
```

| 의존성 | 허용 역할 | 정의 |
|--------|-----------|------|
| `require_superadmin` | SUPERADMIN | `auth/dependencies.py:53` |
| `require_admin_or_above` | SUPERADMIN, ADMIN | `:54` |
| `require_any_role` | SUPERADMIN, ADMIN, STAFF | `:55` ← **CLEANCREW 제외** |
| `require_cleancrew_or_superadmin` | CLEANCREW, SUPERADMIN | `api/cleancrew.py:29` (로컬 정의) |
| `get_current_user` | 로그인한 전원 | 역할 무관 |

**CLEANCREW 는 `/api/clean` 하나만 접근 가능**하다 (`require_any_role` 에서 배제됨).

### 무인증 엔드포인트 — 3개

| 경로 | 판정 |
|------|------|
| `POST /api/auth/login` | ✅ 정상 |
| `POST /api/auth/refresh` | ✅ 정상 |
| `GET /api/template-schedules/custom-types` | 🟡 정적 레지스트리 목록. 민감정보 없으나 무인증 |

`GET /api/events/stream` 은 `Depends` 가 아니라 **쿼리 파라미터 JWT** 를 직접 검증한다 (`_validate_token_and_tenant`) — 무인증 아님.

---

## 1. HTTP 엔드포인트 104개

### `/api/activity-logs` — 2개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/activity-logs` | activity_logs | `get_activity_logs` | 42 | user |
| GET | `/api/activity-logs/stats` | activity_logs | `get_activity_stats` | 35 | user |

### `/api/auth` — 7개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| POST | `/api/auth/login` | auth | `login` | 38 | — |
| GET | `/api/auth/me` | auth | `get_me` | 19 | user |
| POST | `/api/auth/refresh` | auth | `refresh_token` | 19 | — |
| GET | `/api/auth/users` | auth | `list_users` | 35 | admin+ |
| POST | `/api/auth/users` | auth | `create_user` | 47 | admin+ |
| DELETE | `/api/auth/users/{user_id}` | auth | `delete_user` | 36 | admin+ |
| PUT | `/api/auth/users/{user_id}` | auth | `update_user` | 59 | admin+ |

### `/api/buildings` — 5개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/buildings` | buildings | `get_buildings` | 14 | user |
| POST | `/api/buildings` | buildings | `create_building` | 22 | admin+ |
| DELETE | `/api/buildings/{building_id}` | buildings | `delete_building` | 25 | admin+ |
| GET | `/api/buildings/{building_id}` | buildings | `get_building` | 12 | user |
| PUT | `/api/buildings/{building_id}` | buildings | `update_building` | 32 | admin+ |

### `/api/clean` — 1개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/clean` | cleancrew | `list_today_stayover_rooms` | 86 | CLEANCREW+SUPERADMIN |

### `/api/daily-host` — 2개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/daily-host` | daily_host | `get_daily_host` | 9 | admin+ |
| PUT | `/api/daily-host` | daily_host | `upsert_daily_host` | 28 | admin+ |

### `/api/daily-review` — 2개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/daily-review` | daily_review | `get_daily_review` | 9 | admin+ |
| PUT | `/api/daily-review` | daily_review | `upsert_daily_review` | 22 | admin+ |

### `/api/dashboard` — 2개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/dashboard/stats` | dashboard | `get_dashboard_stats` | 123 | user |
| GET | `/api/dashboard/today-schedules` | dashboard | `get_today_schedules` | 117 | user |

### `/api/event-sms` — 2개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| POST | `/api/event-sms/search` | event_sms | `search_reservations` | 100 | user |
| POST | `/api/event-sms/send` | event_sms | `send_event_sms` | 47 | user |

### `/api/events` — 1개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/events/stream` | events | `event_stream` | 40 | JWT(query token) |

### `/api/onsite-female-invites` — 4개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/onsite-female-invites` | onsite_female_invite | `list_invites` | 12 | admin+ |
| POST | `/api/onsite-female-invites` | onsite_female_invite | `add_invite` | 33 | admin+ |
| DELETE | `/api/onsite-female-invites/{invite_id}` | onsite_female_invite | `delete_invite` | 17 | admin+ |
| PATCH | `/api/onsite-female-invites/{invite_id}` | onsite_female_invite | `update_invite` | 44 | admin+ |

### `/api/party-checkin` — 2개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/party-checkin` | party_checkin | `get_party_checkin_list` | 102 | any_role |
| PATCH | `/api/party-checkin/{reservation_id}/toggle` | party_checkin | `toggle_party_checkin` | 62 | any_role |

### `/api/party-hosts` — 3개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/party-hosts` | party_hosts | `list_party_hosts` | 5 | admin+ |
| POST | `/api/party-hosts` | party_hosts | `create_party_host` | 23 | admin+ |
| DELETE | `/api/party-hosts/{host_id}` | party_hosts | `delete_party_host` | 10 | admin+ |

### `/api/reservations` — 18개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/reservations` | reservations | `get_reservations` | 157 | user |
| POST | `/api/reservations` | reservations | `create_reservation` | 57 | user |
| POST | `/api/reservations/detect-consecutive` | reservations_stay | `detect_consecutive_stays` | 13 | user |
| POST | `/api/reservations/sms-send-by-tag` | reservations_sms | `send_sms_by_tag` | 25 | user |
| POST | `/api/reservations/sync/naver` | reservations | `sync_from_naver` | 49 | user |
| DELETE | `/api/reservations/{reservation_id}` | reservations | `delete_reservation` | 106 | user |
| PUT | `/api/reservations/{reservation_id}` | reservations | `update_reservation` | 250 | user |
| PUT | `/api/reservations/{reservation_id}/daily-info` | reservations_room | `update_daily_info` | 53 | user |
| DELETE | `/api/reservations/{reservation_id}/extend-stay` | reservations_stay | `cancel_extend_stay` | 17 | user |
| POST | `/api/reservations/{reservation_id}/extend-stay` | reservations_stay | `extend_stay` | 113 | user |
| POST | `/api/reservations/{reservation_id}/extend-stay/assign-room` | reservations_stay | `extend_stay_assign_room` | 23 | user |
| POST | `/api/reservations/{reservation_id}/reduce-extension` | reservations_stay | `reduce_extension` | 18 | user |
| PUT | `/api/reservations/{reservation_id}/room` | reservations_room | `assign_room` | 111 | user |
| POST | `/api/reservations/{reservation_id}/sms-assign` | reservations_sms | `assign_sms_template` | 36 | user |
| DELETE | `/api/reservations/{reservation_id}/sms-assign/{template_key}` | reservations_sms | `unassign_sms_template` | 24 | user |
| PATCH | `/api/reservations/{reservation_id}/sms-toggle/{template_key}` | reservations_sms | `toggle_sms_sent` | 83 | user |
| POST | `/api/reservations/{reservation_id}/stay-group/link` | reservations_stay | `link_stay_group` | 38 | user |
| DELETE | `/api/reservations/{reservation_id}/stay-group/unlink` | reservations_stay | `unlink_stay_group` | 37 | user |

### `/api/rooms` — 17개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/rooms` | rooms | `get_rooms` | 16 | user |
| POST | `/api/rooms` | rooms | `create_room` | 42 | user |
| POST | `/api/rooms/auto-assign` | rooms | `trigger_auto_assign` | 25 | user |
| PATCH | `/api/rooms/grades` | rooms | `update_room_grades` | 45 | admin+ |
| GET | `/api/rooms/groups` | rooms | `get_room_groups` | 11 | user |
| POST | `/api/rooms/groups` | rooms | `create_room_group` | 21 | admin+ |
| DELETE | `/api/rooms/groups/{group_id}` | rooms | `delete_room_group` | 16 | admin+ |
| PUT | `/api/rooms/groups/{group_id}` | rooms | `update_room_group` | 35 | admin+ |
| GET | `/api/rooms/naver/biz-items` | rooms | `get_naver_biz_items` | 3 | user |
| PATCH | `/api/rooms/naver/biz-items` | rooms | `update_biz_items` | 45 | user |
| POST | `/api/rooms/naver/biz-items/sync` | rooms | `sync_naver_biz_items` | 50 | admin+ |
| POST | `/api/rooms/reorder` | rooms | `reorder_rooms` | 32 | admin+ |
| DELETE | `/api/rooms/{room_id}` | rooms | `delete_room` | 23 | user |
| GET | `/api/rooms/{room_id}` | rooms | `get_room` | 5 | user |
| PUT | `/api/rooms/{room_id}` | rooms | `update_room` | 71 | user |
| POST | `/api/rooms/{room_id}/hide` | rooms | `hide_room` | 76 | user |
| POST | `/api/rooms/{room_id}/unhide` | rooms | `unhide_room` | 32 | user |

### `/api/sales-report` — 1개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/sales-report` | sales_report | `get_sales_report` | 238 | user |

### `/api/scheduler` — 7개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/scheduler/jobs` | scheduler | `get_jobs` | 31 | admin+ |
| GET | `/api/scheduler/jobs/{job_id}` | scheduler | `get_job` | 18 | admin+ |
| POST | `/api/scheduler/jobs/{job_id}/pause` | scheduler | `pause_job` | 20 | admin+ |
| POST | `/api/scheduler/jobs/{job_id}/resume` | scheduler | `resume_job` | 20 | admin+ |
| POST | `/api/scheduler/jobs/{job_id}/run` | scheduler | `run_job_manual` | 35 | admin+ |
| POST | `/api/scheduler/shutdown` | scheduler | `shutdown_scheduler` | 14 | superadmin |
| GET | `/api/scheduler/status` | scheduler | `get_scheduler_status` | 6 | admin+ |

### `/api/settings` — 8개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/settings/highlight-colors` | settings | `get_highlight_colors` | 12 | user |
| PUT | `/api/settings/highlight-colors` | settings | `update_highlight_colors` | 14 | admin+ |
| DELETE | `/api/settings/naver/cookie` | settings | `clear_naver_cookie` | 20 | admin+ |
| POST | `/api/settings/naver/cookie` | settings | `update_naver_cookie` | 67 | admin+ |
| GET | `/api/settings/naver/status` | settings | `get_naver_status` | 33 | user |
| POST | `/api/settings/unstable/settings` | settings | `update_unstable_settings` | 82 | admin+ |
| GET | `/api/settings/unstable/status` | settings | `get_unstable_status` | 31 | user |
| POST | `/api/settings/unstable/sync` | settings | `sync_unstable_reservations` | 26 | admin+ |

### `/api/template-schedules` — 10개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/template-schedules` | template_schedules | `get_schedules` | 16 | user |
| POST | `/api/template-schedules` | template_schedules | `create_schedule` | 115 | admin+ |
| POST | `/api/template-schedules/auto-assign` | template_schedules | `auto_assign` | 45 | user |
| GET | `/api/template-schedules/custom-types` | template_schedules | `get_custom_types` | 3 | 없음 |
| POST | `/api/template-schedules/sync` | template_schedules | `sync_schedules` | 22 | admin+ |
| DELETE | `/api/template-schedules/{schedule_id}` | template_schedules | `delete_schedule` | 36 | admin+ |
| GET | `/api/template-schedules/{schedule_id}` | template_schedules | `get_schedule` | 7 | user |
| PUT | `/api/template-schedules/{schedule_id}` | template_schedules | `update_schedule` | 98 | admin+ |
| GET | `/api/template-schedules/{schedule_id}/preview` | template_schedules | `preview_targets` | 10 | user |
| POST | `/api/template-schedules/{schedule_id}/run` | template_schedules | `run_schedule` | 13 | admin+ |

### `/api/template-variables` — 1개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/template-variables` | templates | `get_available_variables` | 11 | user |

### `/api/templates` — 8개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/templates` | templates | `get_templates` | 41 | user |
| POST | `/api/templates` | templates | `create_template` | 74 | admin+ |
| GET | `/api/templates/labels` | templates | `get_template_labels` | 66 | user |
| POST | `/api/templates/reorder` | templates | `reorder_templates` | 31 | admin+ |
| DELETE | `/api/templates/{template_id}` | templates | `delete_template` | 34 | admin+ |
| GET | `/api/templates/{template_id}` | templates | `get_template` | 26 | user |
| PUT | `/api/templates/{template_id}` | templates | `update_template` | 60 | admin+ |
| POST | `/api/templates/{template_id}/preview` | templates | `preview_template` | 30 | user |

### `/api/tenants` — 1개

| M | 경로 | 파일 | 함수 | LOC | 권한 |
|---|------|------|------|----:|------|
| GET | `/api/tenants` | tenants | `get_tenants` | 23 | user |

<!-- 총 104 -->

---

## 2. 스케줄러 고정 잡 12개

`scheduler/jobs.py:setup_scheduler()` (158줄) 에서 하드코딩 등록. 전부 `Asia/Seoul`.

| # | job id | 시각 | 이름 | 호출 대상 |
|---|--------|------|------|-----------|
| 1 | `sync_naver_reservations` | 5분 간격 | 네이버 예약 동기화 | `naver_sync.sync_naver_to_db` |
| 2 | `sync_unstable_reservations_peak` | 15~20시 / 10분 | 언스테이블 동기화 (피크) | `naver_sync.sync_naver_to_db` (source=unstable) |
| 3 | `sync_unstable_reservations_offpeak` | 00:05 · 12:05 | 언스테이블 동기화 (오프피크) | 〃 |
| 4 | `reconcile_today_reservations` | 09:55 | 네이버 예약 대사 | `naver_sync` (reconcile 모드) |
| 5 | `daily_room_assign` | 10:01 | 객실 자동 배정 | `room_auto_assign.daily_assign_rooms` |
| 6 | `detect_consecutive_stays` | 09·10·11·12시 | 연박 감지 (하루 4회) | `consecutive_stay.detect_and_link_consecutive_stays` |
| 7 | `split_orphan_sweep` | 09:43 | 분할예약 취소고아 정합 | `split_group_guard.sweep_orphan_groups` |
| 8 | `refresh_snapshots_predawn` | 00:50 | 참여자 스냅샷 갱신 (연유 hook 01시 직전) | `templates.variables.refresh_snapshot` |
| 9 | `refresh_snapshots_morning` | 08:50 | 〃 | 〃 |
| 10 | `refresh_snapshots_morning_late` | 09:50 | 〃 | 〃 |
| 11 | `refresh_snapshots_noon` | 11:50 | 〃 | 〃 |
| 12 | `sync_status_log` | 00·06·12·18시 | 동기화 상태 로그 | 내부 |
| — | `load_template_schedules` | `date` (1회) | 기동 시 DB 스케줄 로드 | `schedule_manager` |

> **관측**: 참여자 스냅샷 갱신이 **4번** 등록돼 있다 (00:50 · 08:50 · 09:50 · 11:50). 왜 4회인지, 시각이 다른 잡과 어떤 순서 의존이 있는지는 S3 에서 확인 대상.
> **관측**: 09:43(sweep) → 09:50(스냅샷) → 09:55(대사) → 10:01(자동배정) 이 **7~11분 간격으로 연쇄**한다. 순서 의존이 있다면 명세 대상.

### 동적 잡

`TemplateSchedule` 레코드마다 `schedule_manager.add_schedule_job()` 이 트리거 1개 생성.

| `schedule_type` | 트리거 |
|-----------------|--------|
| `daily` | `CronTrigger(hour, minute)` |
| `weekly` | `CronTrigger(day_of_week, hour, minute)` |
| `hourly` | `CronTrigger` + `active_start_hour`~`active_end_hour` 범위 |
| `interval` | 60분 배수면 `CronTrigger`, 아니면 `IntervalTrigger` (예: 90분) |

---

## 3. DB 전역 이벤트 2개 — **유일한 강제 관문**

| 이벤트 | 위치 | 동작 |
|--------|------|------|
| `Session.before_flush` | `db/tenant_context.py:51` | INSERT 시 `tenant_id` 자동 주입 |
| `Query.before_compile` | `db/tenant_context.py:77` | SELECT 에 `WHERE tenant_id = X` 자동 추가 · 컨텍스트 없으면 **`RuntimeError` (fail-closed)** |

> 이 저장소에서 **우회 불가능하게 강제된 규칙은 이 2개뿐**이다.
> `ReservationMutator`(우회 24곳) · `chip_store` · `RoomAssignment` 쓰기는 전부 관례에 의존한다.
> → S5(코어 경계)에서 어떤 관문을 이 방식으로 승격할지 결정한다.

---

## 4. 미들웨어 4개 (모든 HTTP 요청 통과)

| 순서 | 미들웨어 | 역할 |
|------|----------|------|
| 1 | `CORSMiddleware` | `CORS_ORIGINS` 설정 |
| 2 | `SecurityHeadersMiddleware` | 보안 헤더 |
| 3 | `SlowAPIMiddleware` | 레이트 리밋 (`rate_limit._get_real_ip` — X-Forwarded-For 파싱) |
| 4 | `diag_correlation_middleware` | `req_id` 발급 + `request.enter`/`exit`/`error` diag (INV-1·INV-6 대상, `/health` 스킵) |

## 5. 앱 라이프사이클

| 훅 | 동작 |
|----|------|
| `startup` | `init_db()` (386줄 자동 마이그레이션) → 스케줄러 기동 → DB 스케줄 로드 |
| `shutdown` | 스케줄러 정지 |

---

## 6. 다음 단계에서 확인할 것

- [ ] **E-1** 동적 잡 개수 실측 (운영 `TemplateSchedule` 레코드 수)
- [ ] **E-2** 스냅샷 갱신 4회의 근거 — 시각별로 다른 목적인지, 중복인지
- [ ] **E-3** 09:43~10:01 연쇄 잡의 순서 의존성 (S3 분기 조사와 병행)
- [ ] **E-4** `sync_naver_to_db` 가 4개 잡(1·2·3·4)에서 서로 다른 인자로 호출됨 — 모드별 동작 차이 명세
- [ ] **E-5** 프론트에서 실제 호출되는 엔드포인트 대조 → 죽은 엔드포인트 식별
