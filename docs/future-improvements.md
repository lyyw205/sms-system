# 향후 수정 계획

**작성일**: 2026-03-24
**기반**: 프로젝트 감사 (9명 전문가 에이전트) → Phase 1~6 수정 완료 후 보류 항목 정리

---

## 1. Redis 도입 + 보안 강화

> **선행 작업**: Redis 서버 추가 (docker-compose.yml) + Redis 클라이언트 코드 작성
> **추천 시기**: 보안 요구사항 강화 시 또는 사용자 수 증가 시

### 1-1. JWT 토큰 블랙리스트

**현재 문제**: 직원을 비활성화해도 이미 발급된 JWT 토큰이 최대 1시간 동안 유효. 로그아웃해도 서버에서 토큰을 무효화할 수 없음.

**수정 방법**:
- Redis에 `블랙리스트:{토큰}` 키를 저장, TTL을 토큰 남은 만료시간으로 설정
- `auth/dependencies.py`의 `get_current_user()`에서 매 요청마다 블랙리스트 조회 추가
- 로그아웃 / 사용자 비활성화 시 해당 토큰을 블랙리스트에 등록

**영향 범위**:
- `auth/dependencies.py` — 토큰 검증 로직에 Redis 조회 추가
- `auth/utils.py` — `revoke_token()` 함수 신규
- `api/auth.py` — 로그아웃 엔드포인트에 토큰 무효화 호출

**리스크**: 매 요청마다 Redis 조회 1회 추가 (0.1ms 수준, 체감 없음)

---

### 1-2. SSE 일회성 티켓

**현재 문제**: SSE(실시간 알림) 연결 시 JWT 토큰이 URL 쿼리 파라미터에 노출 (`/api/events/stream?token=eyJhbG...`). 서버 로그, nginx 로그, 브라우저 히스토리에 기록됨.

**수정 방법**:
- `POST /api/events/stream/ticket` — JWT 인증 후 30초짜리 일회용 티켓 발급, Redis에 저장
- `GET /api/events/stream?ticket=xyz` — 티켓으로 인증 (JWT 대신), 사용 즉시 삭제
- 프론트엔드 `api.ts`의 EventSource 연결 코드 수정 (토큰 → 티켓)

**영향 범위**:
- `api/events.py` — 티켓 발급 엔드포인트 신규 + 기존 stream 엔드포인트 수정
- `frontend/src/services/api.ts` 또는 SSE 연결 부분 — 티켓 요청 후 연결

**리스크**: 티켓 만료(30초) 내 연결 못하면 재발급 필요. 프론트 재연결 로직 필요.

---

### 1-3. Refresh Token Rotation

**현재 문제**: Refresh 토큰 사용 시 이전 토큰이 무효화되지 않음. 탈취 시 무한 갱신 가능.

**수정 방법**:
- Redis 또는 DB에 발급된 refresh 토큰 저장
- 갱신 시 이전 토큰 즉시 무효화 (rotation)
- 이미 사용된 토큰으로 갱신 시도 감지 → 해당 사용자의 모든 세션 무효화

**리스크**: DB 기반으로도 구현 가능 (Redis 없이). 단, 성능은 Redis가 유리.

---

## 2. 테스트 인프라 구축

> **추천 시기**: 다음 기능 추가 전

### 2-1. pytest 환경 설정

- `backend/requirements.txt`에 `pytest`, `pytest-asyncio` 추가
- `backend/pytest.ini` 생성 (asyncio_mode = auto)
- `backend/conftest.py` 생성 (FakeReservation fixture 등)

### 2-2. 순수 함수 단위 테스트 (~21건)

DB 없이 즉시 작성 가능한 핵심 비즈니스 로직:

| 테스트 파일 | 대상 함수 | 테스트 수 | 중요도 |
|---|---|---|---|
| `test_apply_buffers.py` | `_apply_buffers()` — 버퍼/반올림 계산 | 7건 | 높음 — SMS 인원수 직결 |
| `test_room_password.py` | `generate_room_password()` — 객실 비밀번호 생성 | 5건 | 중간 |
| `test_consecutive_stay.py` | `compute_is_long_stay()` — 연박 판정 | 4건 | 높음 |
| `test_auth_utils.py` | JWT 발급/검증, 비밀번호 해싱 | 5건 | 높음 |

### 2-3. 멀티테넌트 격리 통합 테스트

- SQLite in-memory DB + tenant_context 검증
- fail-closed 동작 확인 (bypass 없이 테넌트 모델 쿼리 시 RuntimeError)
- bypass_tenant_filter 사용 시 전체 데이터 접근 확인

### 2-4. CI 테스트 연동

- `.github/workflows/deploy.yml:29`에서 `|| echo "No tests found, skipping"` 제거
- 테스트 작성 후에 제거해야 함 (그 전에 제거하면 CI 실패)

---

## 3. 성능 최적화 (스케줄러 백그라운드)

> **추천 시기**: 예약 수가 수백 건을 넘거나, 스케줄이 20개 이상일 때
> **현재 규모에서는 체감 없음** — 모두 백그라운드 스케줄러 작업

### 3-1. `once_per_stay` 루프 N 쿼리

**위치**: `template_scheduler.py:396-426`
**현재**: 연박 예약마다 `EXISTS` 서브쿼리 2회 (기발송 체크)
**수정**: 사전에 `stay_group_id IN (...)` 배치 조회 → Python dict로 검색
**효과**: n=50 연박 → 100 쿼리 → 1 쿼리

### 3-2. SMS 발송 스냅샷 3n 쿼리

**위치**: `variables.py:243-248`
**현재**: SMS 1건마다 tomorrow/yesterday 스냅샷 개별 조회
**수정**: 발송 루프 진입 전 3개 날짜 스냅샷 일괄 조회 → 파라미터로 전달
**효과**: n=30 발송 → 90 쿼리 → 3 쿼리
**주의**: `calculate_template_variables` 인터페이스 변경 필요

### 3-3. `auto_assign_for_schedule` N×D 쿼리

**위치**: `template_scheduler.py:511-534`
**현재**: 예약×날짜 조합마다 `ReservationSmsAssignment` 개별 SELECT
**수정**: `(reservation_id, template_key, date)` 조합을 `IN` 쿼리로 일괄 조회
**효과**: 100건×3일 → 300 쿼리 → 1 쿼리

---

## 4. 구조 리팩토링

> **추천 시기**: 해당 영역에 기능 추가할 때 함께 진행 (점진적 개선)

### 4-1. `auth/dependencies.py` ↔ `api/deps.py` 책임 통합

**현재**: 두 모듈이 서로의 영역을 침범. lazy import로 준-순환 의존 회피 중.
**수정**: `get_current_tenant_id()`에서 user 검증 로직 제거, 순수 테넌트 ID 추출만 담당. 사용자-테넌트 접근 제어는 `auth/dependencies.py`로 통합.
**영향**: 인증 미들웨어 전반, 모든 라우터의 의존성 주입

### 4-2. `api/reservations.py` 분리 (795줄)

**현재**: 예약 CRUD + SMS 발송 + 연박 연결/해제 + 객실 배정 트리거가 한 파일에 혼재
**수정**: `api/reservations_sms.py`, `api/reservations_group.py` 등으로 분리
**영향**: `main.py` 라우터 등록 변경, 프론트엔드 API 경로는 변경 없음

### 4-3. `init_db()` 인라인 SQL → Alembic 이관

**현재**: `database.py`에 260줄의 `ALTER TABLE`/`RENAME COLUMN` SQL이 Alembic과 별도로 존재 (이중 마이그레이션 시스템)
**수정**: 인라인 SQL을 Alembic 마이그레이션으로 이관, `init_db()`는 `create_all()` + seed만 담당
**리스크**: 가장 위험한 변경. 운영 DB에 영향. 유지보수 윈도우 필요.

### 4-4. 날짜 컬럼 String → Date 타입 전환

**현재**: `check_in_date`, `check_out_date`, `confirmed_at` 등이 `String(20)` 타입
**수정**: PostgreSQL 이전 시 `Date`/`DateTime` 타입으로 Alembic 마이그레이션
**시기**: PostgreSQL 본격 전환 시 함께

### 4-5. Frontend God Components 분리

| 파일 | 현재 줄 수 | 분리 대상 |
|---|---|---|
| `Templates.tsx` | 2,339줄 | TemplateForm, ScheduleForm, ScheduleFilterEditor, PreviewModal |
| `RoomAssignment.tsx` | 2,146줄 | RoomColumn, GuestCard, DatePicker, AssignmentFilter |
| `RoomSettings.tsx` | 1,229줄 | RoomForm, BuildingSection, BizItemSection |

**수정**: 도메인별 컴포넌트 디렉토리 생성 (`components/templates/`, `components/room/`)
**권장 기준**: 컴포넌트당 200~400줄

---

## 5. API 개선

> **추천 시기**: 프론트엔드 기능 추가 시 점진적으로

### 5-1. `response_model` 추가 (14개 엔드포인트)

OpenAPI/Swagger 문서에 응답 스키마가 누락된 엔드포인트:
- `activity_logs.py` (2개), `dashboard.py` (2개), `messages.py` (2개)
- `auto_response.py` (3개), `scheduler.py` (7개), `webhooks.py` (1개)
- `settings.py` (2개), `rooms.py` (2개), `templates.py` (1개), `auth.py` (1개)

### 5-2. 페이징 `total` 반환

예약/메시지/로그 목록 API에 총 건수 추가 → 프론트 "더보기" / 페이지네이션 구현 가능

### 5-3. `active` / `is_active` 필드명 통일

현재 혼재: 객실/건물/템플릿/규칙은 `active`, 테넌트만 `is_active`
프론트+백엔드 동시 변경 필요

### 5-4. 웹훅 HMAC 인증

`webhooks.py`의 SMS 수신 엔드포인트에 JWT 대신 HMAC 서명 검증 적용
Aligo API 웹훅 시그니처 방식 조사 필요. 운영 전환 시 구현.

---

## 6. 의존성 & DevOps

### 6-1. 프론트엔드 미사용 패키지 제거

```bash
cd frontend
npm uninstall recharts radix-ui
```

`package-lock.json` 전체 변경되므로 별도 커밋 권장

### 6-2. Python 패키지 버전 고정

```
anthropic>=0.16.0  →  anthropic==0.x.y
PyJWT>=2.8.0       →  PyJWT==2.x.y
bcrypt>=4.0.0      →  bcrypt==x.y.z
slowapi>=0.1.9     →  slowapi==0.1.9
```

정확한 설치 버전 확인 후 고정: `pip freeze | grep -i "anthropic\|pyjwt\|bcrypt\|slowapi"`

### 6-3. nginx 비루트 실행

`frontend/Dockerfile`에서 `nginx:alpine` → 버전 고정 + `user nginx;` 설정

### 6-4. 프로덕션 SHA 태그 배포

`docker-compose.prod.yml`에서 `:latest` 대신 `IMAGE_TAG` 환경변수 사용
`deploy.yml`에서 SHA 전달

### 6-5. Sentry 에러 추적

```bash
pip install sentry-sdk[fastapi]
```

`main.py`에 `sentry_sdk.init(dsn="...")` 1줄 추가
외부 서비스 계정 필요 (무료 플랜 가능)

### 6-6. 배포 실패 Discord 알림

`deploy.yml` 마지막에 `if: failure()` 조건 Discord 알림 스텝 추가

---

## 우선순위 요약

| 순위 | 항목 | 시기 | 난이도 |
|------|------|------|--------|
| 1 | 테스트 인프라 + 단위 테스트 (2장) | 다음 기능 추가 전 | 중 |
| 2 | 프론트엔드 미사용 패키지 제거 (6-1) | 언제든 | 낮음 |
| 3 | Python 패키지 버전 고정 (6-2) | 언제든 | 낮음 |
| 4 | Sentry 도입 (6-5) | 운영 안정화 시 | 낮음 |
| 5 | Redis + JWT 블랙리스트 + SSE 티켓 (1장) | 보안 강화 시 | 높음 |
| 6 | 성능 최적화 (3장) | 규모 성장 시 | 중 |
| 7 | 구조 리팩토링 (4장) | 해당 영역 수정 시 점진적 | 높음 |
| 8 | API 개선 (5장) | 프론트 기능 추가 시 | 중 |
