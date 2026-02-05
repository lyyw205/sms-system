# 구현 계획: SMS 자동 응답 + 예약 관리 + 웹 대시보드 시스템

**상태**: 🔄 진행 중
**시작일**: 2026-02-05
**최종 업데이트**: 2026-02-05
**예상 완료일**: 2026-02-06

---

**⚠️ 중요 지침**: 각 단계 완료 후 반드시:
1. ✅ 완료된 작업 체크박스 확인
2. 🧪 모든 품질 게이트 검증 명령 실행
3. ⚠️ 모든 품질 게이트 항목 통과 확인
4. 📅 위 "최종 업데이트" 날짜 갱신
5. 📝 학습 내용을 노트 섹션에 기록
6. ➡️ 그 다음 단계로 진행

⛔ **품질 게이트를 건너뛰거나 실패한 체크를 무시하지 마세요**

---

## 📋 개요

### 프로젝트 설명
SMS 수신 시 자동으로 응답하는 AI 기반 고객 응대 시스템과 네이버 예약 관리를 통합한 종합 웹 대시보드입니다. 룰 기반 응답과 RAG(Retrieval-Augmented Generation) 기반 응답을 결합하여 정확하고 맥락에 맞는 자동 응답을 제공하며, 예약 상태 변경 시 자동으로 고객에게 SMS 알림을 발송합니다.

**핵심 기능**:
- SMS 자동 수신 및 발신 (국내 SMS API 연동)
- 룰 기반 + RAG 기반 하이브리드 자동 응답
- 네이버 예약 시스템 연동 및 Google Sheets 동기화
- 예약 상태 변경 시 자동 SMS 알림
- 종합 웹 대시보드 (예약 관리, SMS 모니터링, 룰 관리, 문서 관리, 통계)

### 성공 기준
- [ ] SMS 수신 웹훅이 정상적으로 메시지를 수신하고 DB에 저장됨
- [ ] 룰 기반 응답 정확도 ≥95% (정의된 키워드/패턴에 대해)
- [ ] RAG 기반 응답이 관련 문서를 기반으로 응답 생성
- [ ] 네이버 예약 데이터가 자체 DB와 Google Sheets에 정확히 동기화됨
- [ ] 예약 상태 변경 시 자동 SMS 알림 발송 성공률 ≥98%
- [ ] 웹 대시보드의 모든 페이지가 정상 작동하고 데이터 시각화가 정확함
- [ ] E2E 테스트: SMS 수신 → 자동 응답 → 대시보드 이력 확인까지 전체 플로우 성공

### 사용자 영향
- **고객**: 24/7 즉각적인 SMS 자동 응답으로 대기 시간 제거, 예약 상태 변경 시 실시간 알림 수신
- **운영팀**: 수동 SMS 응답 업무 90% 감소, 예약 관리 효율성 향상, 통합 대시보드로 모든 정보 한눈에 파악
- **관리자**: 룰 및 문서 관리를 통한 응답 품질 지속적 개선, 데이터 기반 의사결정 가능

---

## 🏗️ 아키텍처 결정

| 결정 | 근거 | 트레이드오프 |
|------|------|-------------|
| **FastAPI 백엔드** | 비동기 처리 성능 우수, OpenAPI 자동 문서화, Python 생태계 활용 | Node.js 대비 배포 복잡도 약간 증가, 하지만 타입 안정성과 개발 속도 우수 |
| **PostgreSQL 메인 DB** | 트랜잭션 안정성, 복잡한 쿼리 지원, 예약 데이터 무결성 보장 | NoSQL 대비 스키마 변경이 제한적이지만 데이터 일관성 중요한 예약 시스템에 적합 |
| **ChromaDB 벡터 DB** | RAG 파이프라인에 최적화, 간단한 설정, Python 네이티브 지원 | Pinecone/Weaviate 대비 확장성 제한적이지만 초기 프로토타입에 충분 |
| **Redis 캐시/큐** | 중복 메시지 필터, 비동기 작업 큐, 세션 캐싱 | 메모리 사용량 증가하지만 응답 속도와 시스템 안정성 향상 |
| **React + Vite 프론트엔드** | 빠른 개발 속도, 모던 빌드 도구, TypeScript 지원 | Next.js 대비 SSR 부족하지만 대시보드는 CSR로 충분 |
| **Ant Design UI** | 엔터프라이즈급 컴포넌트, 한국어 지원 우수, 테이블/폼 풍부 | shadcn/ui 대비 커스터마이징 제한적이지만 빠른 프로토타이핑 가능 |
| **룰 우선 + RAG 폴백** | 명확한 질문은 룰로 빠르게 응답, 복잡한 질문은 RAG로 유연하게 | 순수 AI 대비 초기 룰 정의 필요하지만 응답 정확도와 비용 효율성 우수 |
| **Google Sheets 동기화** | 기존 워크플로우 유지, 비기술 팀원도 쉽게 접근 | 실시간 동기화 한계 있지만 운영 연속성 보장 |

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                 웹 대시보드 (React)                        │
│  예약관리 | SMS모니터링 | 검토대기큐 | 룰/문서관리 | 통계  │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API + WebSocket (실시간 알림)
┌───────────────────────▼─────────────────────────────────┐
│                FastAPI 백엔드 서버                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐      │
│  │ SMS 모듈  │  │ 예약 모듈 │  │  RAG 파이프라인   │      │
│  │수신/발신  │  │네이버연동 │  │ ChromaDB + LLM   │      │
│  └─────┬────┘  └────┬─────┘  └────────┬──────────┘      │
│        │            │                  │                  │
│  ┌─────▼────────────▼──────────────────▼──────────────┐  │
│  │       메시지 라우터 (룰 → RAG fallback)             │  │
│  └──────────────────┬─────────────────────────────────┘  │
│                     │                                     │
│  ┌──────────────────▼─────────────────────────────────┐  │
│  │       Human-in-the-Loop 판정                        │  │
│  │  confidence ≥ 임계값 → 자동 발송                     │  │
│  │  confidence < 임계값 or 민감 키워드 → 검토 큐        │  │
│  └──────────────────┬─────────────────────────────────┘  │
│                     │                                     │
│  ┌──────────────────▼─────────────────────────────────┐  │
│  │  비동기 처리 (Celery + Redis / BackgroundTasks)      │  │
│  │  중복 수신 필터 → 태스크 큐 → 재시도 (지수 백오프)   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │   DB (PostgreSQL) + Redis (큐/캐시) + Google Sheets │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 프로젝트 구조

```
sms-reservation-system/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI 엔트리포인트
│   │   ├── config.py              # 환경변수 설정
│   │   ├── api/
│   │   │   ├── webhooks.py        # SMS 수신 웹훅
│   │   │   ├── reservations.py    # 예약 관리 API
│   │   │   ├── messages.py        # SMS 이력 API
│   │   │   ├── rules.py           # 룰 관리 API
│   │   │   ├── documents.py       # RAG 문서 관리 API
│   │   │   └── dashboard.py       # 대시보드 통계 API
│   │   ├── sms/
│   │   │   ├── client.py          # SMS 발송 클라이언트
│   │   │   └── models.py          # SMS 데이터 모델
│   │   ├── reservation/
│   │   │   ├── naver_sync.py      # 네이버 예약 연동
│   │   │   ├── google_sheets.py   # Google Sheets 동기화
│   │   │   ├── notifier.py        # 예약 상태 변경 → SMS 알림
│   │   │   └── models.py          # 예약 데이터 모델
│   │   ├── router/
│   │   │   └── message_router.py  # 룰 vs RAG 분기
│   │   ├── rules/
│   │   │   ├── engine.py          # 룰 기반 응답 엔진
│   │   │   └── rules.yaml         # 기본 룰 정의
│   │   ├── rag/
│   │   │   ├── pipeline.py        # RAG 파이프라인
│   │   │   ├── embeddings.py      # 임베딩 처리
│   │   │   ├── vectorstore.py     # ChromaDB 연동
│   │   │   └── llm.py             # LLM 호출
│   │   └── db/
│   │       ├── database.py        # DB 연결 (SQLAlchemy)
│   │       └── models.py          # 전체 DB 모델
│   ├── documents/                 # RAG용 문서 저장소
│   ├── tests/
│   │   ├── unit/                  # 단위 테스트
│   │   ├── integration/           # 통합 테스트
│   │   └── e2e/                   # E2E 테스트
│   ├── alembic/                   # DB 마이그레이션
│   ├── .env
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx      # 메인 대시보드 (통계)
│   │   │   ├── Reservations.tsx   # 예약 관리 (목록/캘린더)
│   │   │   ├── Messages.tsx       # SMS 이력 조회
│   │   │   ├── Rules.tsx          # 응답 룰 관리
│   │   │   └── Documents.tsx      # RAG 문서 관리
│   │   ├── components/
│   │   ├── services/              # API 클라이언트
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
└── docker-compose.yml             # PostgreSQL, ChromaDB, Redis
```

---

## 📦 의존성

### 시작 전 필요사항
- [ ] Python 3.10+ 설치
- [ ] Node.js 18+ 및 npm 설치
- [ ] Docker 및 Docker Compose 설치
- [ ] 국내 SMS API 계정 (NHN Cloud 또는 CoolSMS)
- [ ] Claude API 키 (Anthropic)
- [ ] Google Sheets API 인증 정보 (서비스 계정)
- [ ] 네이버 예약 계정 및 접근 권한

### 백엔드 의존성
```python
# requirements.txt
fastapi==0.110.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
alembic==1.13.1
asyncpg==0.29.0
psycopg2-binary==2.9.9

# RAG & AI
langchain==0.1.6
chromadb==0.4.22
anthropic==0.18.1
openai==1.12.0  # for embeddings

# SMS & External APIs
httpx==0.26.0
aiohttp==3.9.3

# Utils
pyyaml==6.0.1
python-dotenv==1.0.1
pydantic==2.6.1
pydantic-settings==2.1.0

# Google Sheets
gspread==5.12.3
oauth2client==4.1.3

# Task Queue & Cache
celery==5.3.6
redis==5.0.1

# Testing
pytest==8.0.0
pytest-asyncio==0.23.4
pytest-cov==4.1.0
httpx-mock==0.10.0
```

### 프론트엔드 의존성
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "antd": "^5.14.0",
    "axios": "^1.6.7",
    "dayjs": "^1.11.10",
    "recharts": "^2.12.0",
    "@ant-design/icons": "^5.3.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "vite": "^5.1.0",
    "@types/react": "^18.2.55",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "eslint": "^8.56.0",
    "prettier": "^3.2.5",
    "@testing-library/react": "^14.2.1",
    "vitest": "^1.2.2"
  }
}
```

---

## 🧪 테스트 전략

### 테스트 접근법
**TDD 원칙**: 테스트를 먼저 작성하고, 구현으로 통과시키고, 리팩토링으로 개선합니다.

### 테스트 피라미드
| 테스트 유형 | 커버리지 목표 | 목적 |
|------------|--------------|------|
| **단위 테스트** | ≥80% | 비즈니스 로직, 모델, 핵심 알고리즘 검증 |
| **통합 테스트** | 주요 경로 | 컴포넌트 간 상호작용, 데이터 흐름 검증 |
| **E2E 테스트** | 핵심 플로우 | 전체 시스템 동작 검증 (SMS 수신 → 응답 → 대시보드) |

### 단계별 커버리지 요구사항
- **Phase 1 (기반 구축)**: 핵심 모델/엔티티 단위 테스트 (≥80%)
- **Phase 2 (자동 응답)**: 로직 + 리포지토리 테스트 (≥80%)
- **Phase 3 (예약 연동)**: 컴포넌트 통합 테스트 (≥70%)
- **Phase 4 (대시보드)**: E2E 사용자 플로우 테스트 (1개 이상 주요 경로)

### 테스트 명명 규칙
```python
# 백엔드: pytest 스타일
def test_[기능]_[조건]_[예상결과]():
    # Arrange: 테스트 데이터 준비
    # Act: 테스트 대상 실행
    # Assert: 결과 검증

# 예시
def test_rule_engine_matches_keyword_returns_response():
    ...
```

```typescript
// 프론트엔드: Vitest 스타일
describe('컴포넌트/기능명', () => {
  test('조건 → 예상결과', () => {
    // Arrange → Act → Assert
  })
})
```

---

## 🚀 구현 단계

### Phase 1: 기반 구축 + SMS 연동
**목표**: FastAPI 백엔드 구조 완성 및 SMS 수신/발신 기능 작동
**예상 시간**: 3시간
**상태**: ⏳ 대기 중

#### 작업

**🔴 RED: 실패하는 테스트 먼저 작성**

- [ ] **테스트 1.1**: DB 모델 단위 테스트 작성
  - 파일: `backend/tests/unit/db/test_models.py`
  - 예상: 테스트 실패 (모델이 아직 존재하지 않음)
  - 세부사항:
    - `Message` 모델 생성 및 필드 검증 테스트
    - `Reservation` 모델 생성 및 관계 테스트
    - `Rule` 모델 YAML 파싱 테스트
    - `Document` 모델 메타데이터 저장 테스트
  - 테스트 케이스:
    - Happy path: 유효한 데이터로 모델 생성
    - Edge case: 필수 필드 누락 시 에러
    - Error: 잘못된 데이터 타입 시 예외 발생

- [ ] **테스트 1.2**: SMS 클라이언트 단위 테스트 작성 (모의 객체 사용)
  - 파일: `backend/tests/unit/sms/test_client.py`
  - 예상: 테스트 실패 (SMS 클라이언트 미구현)
  - 세부사항:
    - SMS 발송 성공 시나리오
    - SMS 발송 실패 시 재시도 로직
    - API 에러 핸들링 (네트워크 오류, 인증 실패 등)
  - 모의 객체: `httpx.AsyncClient`를 모의하여 실제 API 호출 없이 테스트

- [ ] **테스트 1.3**: 웹훅 엔드포인트 통합 테스트 작성
  - 파일: `backend/tests/integration/api/test_webhooks.py`
  - 예상: 테스트 실패 (엔드포인트 미구현)
  - 세부사항:
    - SMS 수신 웹훅 POST 요청 → DB 저장 확인
    - 중복 메시지 필터링 (Redis 캐시 활용)
    - 잘못된 페이로드 처리
  - 테스트 시나리오:
    - 정상 SMS 수신 → 201 Created 응답 + DB 레코드 생성
    - 중복 메시지 → 200 OK (중복 처리) + DB 레코드 미생성
    - 잘못된 JSON → 400 Bad Request

**🟢 GREEN: 테스트를 통과시키는 최소 구현**

- [ ] **작업 1.4**: 프로젝트 초기 설정
  - 파일: `backend/app/`, `docker-compose.yml`, `.env.example`
  - 목표: FastAPI 기본 구조 생성, Docker Compose 실행 가능
  - 세부사항:
    - FastAPI 앱 생성 (`app/main.py`)
    - CORS 미들웨어 설정
    - 환경변수 관리 (`app/config.py` + `pydantic-settings`)
    - Docker Compose: PostgreSQL, ChromaDB, Redis 컨테이너
    - `.env.example` 파일 생성
  - 검증: `docker-compose up -d` 성공, `http://localhost:8000/docs` 접근 가능

- [ ] **작업 1.5**: DB 모델 구현 (SQLAlchemy)
  - 파일: `backend/app/db/models.py`, `backend/app/db/database.py`
  - 목표: 테스트 1.1 통과
  - 세부사항:
    - `Message` 모델: id, sender, receiver, content, direction, status, created_at
    - `Reservation` 모델: id, customer_name, phone, date, time, status, notes
    - `Rule` 모델: id, name, pattern, response_template, priority, enabled
    - `Document` 모델: id, filename, content_hash, metadata, indexed_at
    - Alembic 마이그레이션 초기화 및 첫 마이그레이션 생성
  - 검증: `alembic upgrade head` 성공, 테스트 1.1 통과

- [ ] **작업 1.6**: SMS API 클라이언트 구현
  - 파일: `backend/app/sms/client.py`
  - 목표: 테스트 1.2 통과
  - 세부사항:
    - `SMSClient` 클래스 생성 (httpx.AsyncClient 사용)
    - `send_sms(to: str, message: str)` 메서드
    - API 인증 헤더 처리
    - 에러 핸들링 및 로깅
    - 재시도 로직 (tenacity 라이브러리 또는 수동 구현)
  - 검증: 테스트 1.2 통과 (모의 객체로 API 호출 성공/실패 시나리오)

- [ ] **작업 1.7**: SMS 수신 웹훅 엔드포인트 구현
  - 파일: `backend/app/api/webhooks.py`
  - 목표: 테스트 1.3 통과
  - 세부사항:
    - `POST /webhooks/sms` 엔드포인트 생성
    - 요청 바디 검증 (Pydantic 스키마)
    - Redis를 사용한 중복 메시지 체크 (메시지 ID 해싱)
    - DB에 메시지 저장 (`Message` 모델)
    - 에러 응답 처리 (400, 500)
  - 검증: 테스트 1.3 통과, ngrok으로 실제 SMS 수신 테스트 (선택)

- [ ] **작업 1.8**: SMS 이력 조회 API 구현
  - 파일: `backend/app/api/messages.py`
  - 목표: SMS 이력 CRUD API 완성
  - 세부사항:
    - `GET /api/messages` (목록 조회, 페이지네이션)
    - `GET /api/messages/{id}` (상세 조회)
    - `POST /api/messages/send` (수동 발송)
  - 검증: Swagger UI에서 API 호출 테스트

**🔵 REFACTOR: 코드 품질 개선**

- [ ] **작업 1.9**: 설정 및 코드 리팩토링
  - 파일: 전체 Phase 1 코드
  - 목표: 테스트를 유지하며 코드 품질 향상
  - 체크리스트:
    - [ ] 중복 코드 제거 (DRY 원칙)
    - [ ] 변수 및 함수명 명확화
    - [ ] 환경변수 검증 로직 추가 (config.py)
    - [ ] 에러 메시지 표준화
    - [ ] 로깅 추가 (structlog 또는 기본 logging)
    - [ ] Docstring 추가 (주요 함수/클래스)
  - 검증: 모든 테스트 여전히 통과, 코드 가독성 향상

#### Quality Gate ✋

**⚠️ STOP: Phase 2로 진행하기 전에 모든 체크 통과 확인**

**TDD 준수** (필수):
- [ ] **Red 단계**: 테스트를 먼저 작성했고 초기에 실패함
- [ ] **Green 단계**: 프로덕션 코드를 작성하여 테스트 통과
- [ ] **Refactor 단계**: 테스트를 유지하며 코드 개선 완료
- [ ] **커버리지 확인**: 단위 테스트 커버리지 ≥80%
  ```bash
  cd backend
  pytest --cov=app --cov-report=html --cov-report=term
  # 목표: app/db, app/sms 모듈 ≥80%
  ```

**빌드 & 테스트**:
- [ ] **빌드**: Docker Compose 정상 실행 (`docker-compose up -d`)
- [ ] **모든 테스트 통과**: `pytest` 실행 시 100% 통과
- [ ] **테스트 성능**: 테스트 스위트 5분 이내 완료
- [ ] **안정성**: 테스트 3회 연속 실행 시 모두 통과

**코드 품질**:
- [ ] **린트**: `ruff check .` 또는 `flake8` 에러 없음
- [ ] **포맷**: `black --check .` 통과
- [ ] **타입 체크**: `mypy app/` 통과 (설정된 경우)

**기능 검증**:
- [ ] **DB 마이그레이션**: `alembic upgrade head` 성공
- [ ] **API 문서**: `http://localhost:8000/docs` 접근 가능
- [ ] **SMS 발송 테스트**: Swagger UI에서 수동 발송 성공 (실제 API 사용 시)
- [ ] **웹훅 수신**: ngrok 또는 로컬 curl로 웹훅 POST 요청 → DB 저장 확인

**보안 & 성능**:
- [ ] **의존성 취약점**: `pip-audit` 실행, 심각한 취약점 없음
- [ ] **환경변수 보호**: `.env` 파일이 `.gitignore`에 포함됨
- [ ] **API 인증**: SMS API 키가 코드에 하드코딩되지 않음

**문서화**:
- [ ] **README 업데이트**: 프로젝트 설정 방법 문서화
- [ ] **API 주석**: 주요 엔드포인트에 docstring 추가
- [ ] **.env.example**: 필요한 환경변수 모두 나열

**검증 명령**:
```bash
# Docker 컨테이너 실행
docker-compose up -d
docker ps  # PostgreSQL, Redis, ChromaDB 실행 확인

# DB 마이그레이션
cd backend
alembic upgrade head

# 테스트 실행
pytest --cov=app --cov-report=html --cov-report=term
# 커버리지 목표: ≥80%

# 코드 품질 체크
ruff check .
black --check .
mypy app/

# 보안 체크
pip-audit

# API 서버 실행
uvicorn app.main:app --reload
# 브라우저에서 http://localhost:8000/docs 접근
```

**수동 테스트 체크리스트**:
- [ ] Swagger UI에서 `GET /api/messages` 호출 → 빈 배열 또는 샘플 데이터 반환
- [ ] Swagger UI에서 `POST /webhooks/sms` 호출 → 201 Created 응답
- [ ] DB 확인: `docker exec -it <postgres-container> psql -U user -d sms_db -c "SELECT * FROM messages;"`
- [ ] Redis 확인: 중복 메시지 발송 시 중복 필터링 작동

---

### Phase 2: 자동 응답 엔진 (룰 + RAG)
**목표**: 룰 기반 및 RAG 기반 자동 응답 시스템 완성
**예상 시간**: 4시간
**상태**: ⏳ 대기 중

#### 작업

**🔴 RED: 실패하는 테스트 먼저 작성**

- [ ] **테스트 2.1**: 룰 엔진 단위 테스트 작성
  - 파일: `backend/tests/unit/rules/test_engine.py`
  - 예상: 테스트 실패 (룰 엔진 미구현)
  - 세부사항:
    - 키워드 매칭 테스트 (예: "예약" → 예약 안내 응답)
    - 정규식 패턴 매칭 테스트 (예: "\\d{4}-\\d{2}-\\d{2}" → 날짜 인식)
    - 우선순위 테스트 (높은 우선순위 룰 먼저 매칭)
    - 룰 미매칭 시 `None` 반환
  - 테스트 데이터: `tests/fixtures/test_rules.yaml`

- [ ] **테스트 2.2**: RAG 파이프라인 통합 테스트 작성
  - 파일: `backend/tests/integration/rag/test_pipeline.py`
  - 예상: 테스트 실패 (RAG 파이프라인 미구현)
  - 세부사항:
    - 문서 인덱싱 테스트 (PDF, TXT 업로드 → ChromaDB 저장)
    - 벡터 검색 테스트 (질문 → 관련 문서 조각 반환)
    - LLM 응답 생성 테스트 (컨텍스트 + 질문 → 응답)
    - 응답 신뢰도 점수 테스트
  - 모의 객체: `anthropic.Anthropic` 클라이언트 모의

- [ ] **테스트 2.3**: 메시지 라우터 통합 테스트 작성
  - 파일: `backend/tests/integration/router/test_message_router.py`
  - 예상: 테스트 실패 (메시지 라우터 미구현)
  - 세부사항:
    - 룰 매칭 성공 → 룰 응답 반환
    - 룰 매칭 실패 → RAG로 폴백
    - 신뢰도 낮음 → Human-in-the-Loop 큐로 전송
    - 민감 키워드 감지 → 검토 큐로 전송

**🟢 GREEN: 테스트를 통과시키는 최소 구현**

- [ ] **작업 2.4**: 룰 엔진 구현
  - 파일: `backend/app/rules/engine.py`, `backend/app/rules/rules.yaml`
  - 목표: 테스트 2.1 통과
  - 세부사항:
    - `RuleEngine` 클래스 생성
    - YAML 파일에서 룰 로드 (pyyaml)
    - 룰 구조: `pattern` (regex/keyword), `response_template`, `priority`
    - `match(message: str) -> Optional[str]` 메서드 구현
    - 우선순위 정렬 후 순차 매칭
  - 기본 룰 예시:
    ```yaml
    rules:
      - name: "영업시간 문의"
        pattern: "영업시간|몇 시|언제"
        response: "영업시간은 오전 10시부터 오후 8시까지입니다."
        priority: 10
      - name: "예약 문의"
        pattern: "예약|예약하기"
        response: "예약은 네이버 예약을 통해 가능합니다: [링크]"
        priority: 5
    ```
  - 검증: 테스트 2.1 통과

- [ ] **작업 2.5**: RAG 파이프라인 구현
  - 파일: `backend/app/rag/pipeline.py`, `backend/app/rag/vectorstore.py`, `backend/app/rag/llm.py`, `backend/app/rag/embeddings.py`
  - 목표: 테스트 2.2 통과
  - 세부사항:
    - **문서 로더** (`pipeline.py`):
      - PDF, TXT, XLSX 파일 파싱 (pypdf, openpyxl)
      - 텍스트 청킹 (langchain.text_splitter)
    - **임베딩** (`embeddings.py`):
      - OpenAI Embeddings 또는 HuggingFace 모델
      - 문서 청크 → 임베딩 벡터 변환
    - **벡터 스토어** (`vectorstore.py`):
      - ChromaDB 클라이언트 초기화
      - `add_documents()`, `similarity_search()` 메서드
    - **LLM 호출** (`llm.py`):
      - Anthropic Claude API 호출
      - 프롬프트 템플릿: "다음 정보를 참고하여 질문에 답변하세요: {context}\n\n질문: {question}"
      - 응답 + 신뢰도 점수 반환
  - 검증: 테스트 2.2 통과

- [ ] **작업 2.6**: 메시지 라우터 구현
  - 파일: `backend/app/router/message_router.py`
  - 목표: 테스트 2.3 통과
  - 세부사항:
    - `MessageRouter` 클래스
    - `route(message: str) -> Response` 메서드:
      1. 룰 엔진 시도
      2. 룰 매칭 성공 → 즉시 반환
      3. 룰 매칭 실패 → RAG 파이프라인 호출
      4. RAG 신뢰도 ≥ 임계값 (예: 0.7) → 자동 응답
      5. RAG 신뢰도 < 임계값 → Human-in-the-Loop 큐
    - 민감 키워드 체크 (예: "환불", "취소", "불만")
  - 검증: 테스트 2.3 통과

- [ ] **작업 2.7**: 룰 관리 API 구현
  - 파일: `backend/app/api/rules.py`
  - 목표: 웹 대시보드에서 룰 CRUD 가능
  - 세부사항:
    - `GET /api/rules` (룰 목록)
    - `POST /api/rules` (룰 생성)
    - `PUT /api/rules/{id}` (룰 수정)
    - `DELETE /api/rules/{id}` (룰 삭제)
    - 룰 변경 시 메모리에 핫 리로드
  - 검증: Swagger UI에서 CRUD 테스트

- [ ] **작업 2.8**: 문서 관리 API 구현
  - 파일: `backend/app/api/documents.py`
  - 목표: RAG 문서 업로드 및 관리
  - 세부사항:
    - `POST /api/documents/upload` (파일 업로드 → 인덱싱)
    - `GET /api/documents` (문서 목록)
    - `DELETE /api/documents/{id}` (문서 삭제 → 벡터 DB에서도 제거)
  - 검증: Swagger UI에서 파일 업로드 → 인덱싱 성공 확인

**🔵 REFACTOR: 코드 품질 개선**

- [ ] **작업 2.9**: 자동 응답 엔진 리팩토링
  - 파일: 전체 Phase 2 코드
  - 목표: 테스트를 유지하며 코드 품질 향상
  - 체크리스트:
    - [ ] 룰 엔진과 RAG 파이프라인의 인터페이스 통일
    - [ ] 프롬프트 템플릿 외부 설정 파일로 분리
    - [ ] LLM 호출 비용 최적화 (캐싱, 토큰 제한)
    - [ ] 에러 핸들링 강화 (LLM API 타임아웃, 네트워크 오류)
    - [ ] 로깅 추가 (룰 매칭 성공/실패, RAG 호출 내역)
  - 검증: 모든 테스트 여전히 통과

#### Quality Gate ✋

**⚠️ STOP: Phase 3로 진행하기 전에 모든 체크 통과 확인**

**TDD 준수** (필수):
- [ ] **Red 단계**: 테스트를 먼저 작성했고 초기에 실패함
- [ ] **Green 단계**: 프로덕션 코드를 작성하여 테스트 통과
- [ ] **Refactor 단계**: 테스트를 유지하며 코드 개선 완료
- [ ] **커버리지 확인**: 단위 + 통합 테스트 커버리지 ≥80%
  ```bash
  pytest --cov=app.rules --cov=app.rag --cov=app.router --cov-report=html
  ```

**빌드 & 테스트**:
- [ ] **모든 테스트 통과**: `pytest` 실행 시 100% 통과
- [ ] **안정성**: 테스트 3회 연속 실행 시 모두 통과
- [ ] **통합 테스트**: 룰 → RAG 폴백 플로우 정상 작동

**기능 검증**:
- [ ] **룰 매칭 정확도**: 테스트 케이스 10개 이상, 정확도 ≥95%
- [ ] **RAG 응답 생성**: 샘플 문서 인덱싱 → 질문 → 관련 응답 생성 확인
- [ ] **메시지 라우터**: 룰 매칭 성공 시나리오 및 RAG 폴백 시나리오 모두 테스트
- [ ] **Human-in-the-Loop**: 신뢰도 낮은 응답이 검토 큐에 저장되는지 확인

**RAG 품질**:
- [ ] **문서 인덱싱**: PDF, TXT 파일 업로드 → ChromaDB에 저장 확인
  ```bash
  # ChromaDB 데이터 확인 (Python REPL)
  python -c "import chromadb; client = chromadb.PersistentClient(path='./chroma_data'); print(client.list_collections())"
  ```
- [ ] **벡터 검색**: 유사도 상위 3개 문서 조각 반환
- [ ] **응답 품질**: 생성된 응답이 검색된 문서와 관련성 있음 (수동 검토)

**보안 & 성능**:
- [ ] **API 키 보호**: Claude API 키가 환경변수로 관리됨
- [ ] **LLM 비용 제어**: 토큰 제한 설정 (max_tokens)
- [ ] **응답 시간**: RAG 응답 생성 시간 ≤5초 (평균)

**문서화**:
- [ ] **룰 작성 가이드**: YAML 룰 형식 및 예시 문서화
- [ ] **RAG 사용법**: 문서 업로드 및 인덱싱 방법 README에 추가

**검증 명령**:
```bash
# 테스트 실행
pytest tests/unit/rules tests/integration/rag tests/integration/router -v

# 커버리지 체크
pytest --cov=app.rules --cov=app.rag --cov=app.router --cov-report=term

# 룰 엔진 수동 테스트 (Python REPL)
python -c "from app.rules.engine import RuleEngine; engine = RuleEngine(); print(engine.match('영업시간 알려주세요'))"

# RAG 파이프라인 테스트
# 1. 샘플 문서 업로드 (Swagger UI 또는 curl)
curl -X POST http://localhost:8000/api/documents/upload -F "file=@sample.pdf"
# 2. 질문 테스트
curl -X POST http://localhost:8000/api/test-rag -H "Content-Type: application/json" -d '{"question": "영업시간이 어떻게 되나요?"}'
```

**수동 테스트 체크리스트**:
- [ ] 룰 매칭: "예약하고 싶어요" 입력 → 예약 안내 응답 반환
- [ ] RAG 응답: 문서 업로드 후 관련 질문 → 문서 기반 응답 생성
- [ ] 폴백: 룰에 없는 질문 → RAG로 자동 전환
- [ ] Human-in-the-Loop: 애매한 질문 → 검토 큐에 저장 확인

---

### Phase 3: 예약 연동 + 자동 알림
**목표**: 네이버 예약 동기화 및 예약 상태 변경 시 자동 SMS 알림 발송
**예상 시간**: 4시간
**상태**: ⏳ 대기 중

#### 작업

**🔴 RED: 실패하는 테스트 먼저 작성**

- [ ] **테스트 3.1**: 네이버 예약 동기화 통합 테스트 작성
  - 파일: `backend/tests/integration/reservation/test_naver_sync.py`
  - 예상: 테스트 실패 (동기화 로직 미구현)
  - 세부사항:
    - 네이버 예약 데이터 가져오기 (API 또는 크롤링)
    - 신규 예약 → DB에 INSERT
    - 기존 예약 변경 → DB에 UPDATE
    - 취소된 예약 → status 변경
  - 모의 객체: 네이버 API 응답 모의

- [ ] **테스트 3.2**: Google Sheets 동기화 통합 테스트 작성
  - 파일: `backend/tests/integration/reservation/test_google_sheets.py`
  - 예상: 테스트 실패 (Google Sheets 연동 미구현)
  - 세부사항:
    - DB 예약 데이터 → Google Sheets 쓰기
    - Google Sheets 데이터 → DB로 읽기 (양방향)
    - 충돌 해결 전략 (타임스탬프 기반)
  - 모의 객체: gspread 클라이언트 모의

- [ ] **테스트 3.3**: 예약 상태 변경 알림 단위 테스트 작성
  - 파일: `backend/tests/unit/reservation/test_notifier.py`
  - 예상: 테스트 실패 (알림 로직 미구현)
  - 세부사항:
    - 신규 예약 → "예약이 접수되었습니다" SMS 발송
    - 예약 확정 → "예약이 확정되었습니다" SMS 발송
    - 예약 취소 → "예약이 취소되었습니다" SMS 발송
    - 예약 변경 → "예약 시간이 변경되었습니다" SMS 발송
  - 모의 객체: SMS 클라이언트 모의

**🟢 GREEN: 테스트를 통과시키는 최소 구현**

- [ ] **작업 3.4**: 네이버 예약 연동 구현
  - 파일: `backend/app/reservation/naver_sync.py`
  - 목표: 테스트 3.1 통과
  - 세부사항:
    - **Option A (공식 API 사용 가능 시)**:
      - 네이버 예약 API 클라이언트 구현
      - OAuth 인증 처리
      - 예약 데이터 GET 엔드포인트 호출
    - **Option B (크롤링 필요 시)**:
      - Selenium 또는 Playwright로 네이버 예약 페이지 크롤링
      - 로그인 자동화 (credentials 환경변수)
      - 예약 목록 파싱
    - 주기적 동기화 (APScheduler, 5분마다)
    - 데이터 변환 (네이버 형식 → DB 모델)
  - 검증: 테스트 3.1 통과

- [ ] **작업 3.5**: Google Sheets 양방향 동기화 구현
  - 파일: `backend/app/reservation/google_sheets.py`
  - 목표: 테스트 3.2 통과
  - 세부사항:
    - gspread 라이브러리 사용
    - 서비스 계정 인증 (JSON 키 파일)
    - `sync_to_sheets()`: DB → Google Sheets 쓰기
    - `sync_from_sheets()`: Google Sheets → DB 읽기
    - 충돌 해결: `updated_at` 타임스탬프 비교, 최신 데이터 우선
    - 주기적 동기화 (10분마다)
  - 검증: 테스트 3.2 통과

- [ ] **작업 3.6**: 예약 상태 변경 알림 시스템 구현
  - 파일: `backend/app/reservation/notifier.py`
  - 목표: 테스트 3.3 통과
  - 세부사항:
    - `ReservationNotifier` 클래스
    - DB 트리거 또는 SQLAlchemy 이벤트 리스너:
      - `after_insert` → 신규 예약 알림
      - `after_update` → 상태 변경 알림
    - SMS 템플릿 관리 (Jinja2 템플릿)
    - 예시 템플릿:
      ```
      [업체명] 예약이 {{ status }}되었습니다.
      - 예약자: {{ customer_name }}
      - 일시: {{ date }} {{ time }}
      감사합니다.
      ```
    - 비동기 발송 (Celery 태스크 또는 BackgroundTasks)
  - 검증: 테스트 3.3 통과

- [ ] **작업 3.7**: 예약 관리 API 구현
  - 파일: `backend/app/api/reservations.py`
  - 목표: 웹 대시보드에서 예약 CRUD 가능
  - 세부사항:
    - `GET /api/reservations` (목록, 필터, 페이지네이션)
    - `GET /api/reservations/{id}` (상세)
    - `POST /api/reservations` (수동 생성)
    - `PUT /api/reservations/{id}` (수정 → 알림 트리거)
    - `DELETE /api/reservations/{id}` (삭제)
  - 검증: Swagger UI에서 CRUD 테스트

**🔵 REFACTOR: 코드 품질 개선**

- [ ] **작업 3.8**: 예약 연동 로직 리팩토링
  - 파일: 전체 Phase 3 코드
  - 목표: 테스트를 유지하며 코드 품질 향상
  - 체크리스트:
    - [ ] 동기화 로직 최적화 (배치 처리, 증분 업데이트)
    - [ ] 중복 알림 방지 (Redis 캐시로 이미 발송한 알림 추적)
    - [ ] 에러 핸들링 강화 (네이버 API 타임아웃, Google Sheets 권한 오류)
    - [ ] 로깅 추가 (동기화 성공/실패, 알림 발송 내역)
    - [ ] SMS 템플릿 DB로 이동 (동적 수정 가능)
  - 검증: 모든 테스트 여전히 통과

#### Quality Gate ✋

**⚠️ STOP: Phase 4로 진행하기 전에 모든 체크 통과 확인**

**TDD 준수** (필수):
- [ ] **Red 단계**: 테스트를 먼저 작성했고 초기에 실패함
- [ ] **Green 단계**: 프로덕션 코드를 작성하여 테스트 통과
- [ ] **Refactor 단계**: 테스트를 유지하며 코드 개선 완료
- [ ] **커버리지 확인**: 통합 테스트 커버리지 ≥70%
  ```bash
  pytest --cov=app.reservation --cov-report=html
  ```

**빌드 & 테스트**:
- [ ] **모든 테스트 통과**: `pytest` 실행 시 100% 통과
- [ ] **안정성**: 테스트 3회 연속 실행 시 모두 통과
- [ ] **동기화 테스트**: 네이버 예약 → DB → Google Sheets 전체 플로우 검증

**기능 검증**:
- [ ] **네이버 예약 동기화**: 실제 네이버 예약 계정으로 테스트 (또는 샌드박스)
  - 신규 예약 생성 → DB에 반영됨
  - 예약 취소 → DB 상태 변경됨
- [ ] **Google Sheets 동기화**:
  - DB 예약 생성 → Google Sheets에 행 추가됨
  - Google Sheets 수정 → DB에 반영됨
  - 충돌 시 최신 데이터 우선 적용
- [ ] **SMS 알림 발송**:
  - 신규 예약 → SMS 발송 확인 (실제 번호 또는 테스트 번호)
  - 상태 변경 → 해당 템플릿 SMS 발송 확인
  - 발송 성공률 ≥98%

**데이터 무결성**:
- [ ] **중복 방지**: 동일 예약이 여러 번 동기화되어도 DB에 중복 레코드 없음
- [ ] **트랜잭션**: 동기화 실패 시 부분 업데이트 없이 롤백
- [ ] **타임스탬프**: 모든 예약에 `created_at`, `updated_at` 정확히 기록

**보안 & 성능**:
- [ ] **API 키 보호**: 네이버 API 키, Google 서비스 계정 키가 환경변수로 관리
- [ ] **권한 관리**: Google Sheets 서비스 계정에 최소 권한만 부여
- [ ] **동기화 성능**: 100개 예약 동기화 시간 ≤30초

**문서화**:
- [ ] **동기화 설정 가이드**: 네이버 예약 API 설정 방법 문서화
- [ ] **Google Sheets 설정**: 서비스 계정 생성 및 시트 공유 방법 README에 추가

**검증 명령**:
```bash
# 테스트 실행
pytest tests/integration/reservation -v

# 동기화 수동 실행
python -m app.reservation.naver_sync  # 또는 스케줄러 트리거
python -m app.reservation.google_sheets

# DB 확인
docker exec -it <postgres-container> psql -U user -d sms_db -c "SELECT * FROM reservations ORDER BY created_at DESC LIMIT 10;"

# Google Sheets 확인 (브라우저에서 시트 열기)

# SMS 발송 로그 확인
tail -f logs/app.log | grep "SMS sent"
```

**수동 테스트 체크리스트**:
- [ ] 네이버 예약에서 신규 예약 생성 → 5분 내 DB 반영 확인
- [ ] DB에서 예약 상태 변경 → SMS 알림 수신 확인
- [ ] Google Sheets에서 예약 수정 → 10분 내 DB 반영 확인
- [ ] 충돌 시나리오: DB와 Google Sheets 동시 수정 → 최신 데이터 적용 확인

---

### Phase 4: 웹 대시보드 전체
**목표**: React 기반 종합 웹 대시보드 완성 (예약 관리, SMS 모니터링, 룰/문서 관리, 통계)
**예상 시간**: 4시간
**상태**: ⏳ 대기 중

#### 작업

**🔴 RED: 실패하는 테스트 먼저 작성**

- [ ] **테스트 4.1**: API 클라이언트 단위 테스트 작성
  - 파일: `frontend/src/services/__tests__/api.test.ts`
  - 예상: 테스트 실패 (API 클라이언트 미구현)
  - 세부사항:
    - `getReservations()` 호출 → 목록 반환
    - `updateReservation()` 호출 → 성공 응답
    - 에러 핸들링 (401, 500)
  - 모의 객체: axios 모의

- [ ] **테스트 4.2**: 주요 컴포넌트 단위 테스트 작성
  - 파일: `frontend/src/pages/__tests__/Dashboard.test.tsx`
  - 예상: 테스트 실패 (컴포넌트 미구현)
  - 세부사항:
    - 대시보드 렌더링
    - 통계 데이터 표시
    - 차트 렌더링
  - Testing Library 사용

- [ ] **테스트 4.3**: E2E 테스트 작성 (선택)
  - 파일: `frontend/e2e/reservation-flow.spec.ts`
  - 예상: 테스트 실패 (전체 플로우 미완성)
  - 세부사항:
    - 예약 목록 페이지 접속
    - 새 예약 생성 버튼 클릭
    - 폼 입력 후 저장
    - 목록에 새 예약 표시 확인
  - Playwright 또는 Cypress 사용

**🟢 GREEN: 테스트를 통과시키는 최소 구현**

- [ ] **작업 4.4**: 프론트엔드 프로젝트 초기 설정
  - 파일: `frontend/`, `package.json`, `vite.config.ts`
  - 목표: React + Vite + TypeScript 프로젝트 생성
  - 세부사항:
    ```bash
    npm create vite@latest frontend -- --template react-ts
    cd frontend
    npm install
    npm install antd @ant-design/icons axios dayjs recharts zustand
    npm install -D @testing-library/react @testing-library/jest-dom vitest
    ```
  - 검증: `npm run dev` 실행 → `http://localhost:5173` 접근 가능

- [ ] **작업 4.5**: 라우팅 및 레이아웃 구현
  - 파일: `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`
  - 목표: 기본 네비게이션 구조 완성
  - 세부사항:
    - React Router v6 설정
    - 라우트: `/`, `/reservations`, `/messages`, `/rules`, `/documents`
    - Ant Design Layout 컴포넌트 (Sider + Header + Content)
    - 사이드바 메뉴 (Dashboard, Reservations, Messages, Rules, Documents)
  - 검증: 각 메뉴 클릭 시 페이지 전환

- [ ] **작업 4.6**: API 연동 레이어 구현
  - 파일: `frontend/src/services/api.ts`
  - 목표: 테스트 4.1 통과
  - 세부사항:
    - axios 인스턴스 생성 (baseURL: `http://localhost:8000/api`)
    - API 함수들:
      - `getReservations()`, `createReservation()`, `updateReservation()`, `deleteReservation()`
      - `getMessages()`, `sendMessage()`
      - `getRules()`, `createRule()`, `updateRule()`, `deleteRule()`
      - `getDocuments()`, `uploadDocument()`, `deleteDocument()`
      - `getDashboardStats()`
    - 에러 인터셉터 (401 → 로그인 리다이렉트, 500 → 에러 토스트)
  - 검증: 테스트 4.1 통과

- [ ] **작업 4.7**: 메인 대시보드 페이지 구현
  - 파일: `frontend/src/pages/Dashboard.tsx`
  - 목표: 테스트 4.2 통과, 주요 통계 시각화
  - 세부사항:
    - 상단 통계 카드 (오늘 예약 수, 전체 메시지 수, 자동 응답률)
    - 최근 예약 목록 (간단한 테이블)
    - 최근 SMS 이력 (타임라인)
    - 응답 유형 차트 (룰 vs RAG, Pie Chart)
    - recharts 라이브러리 사용
  - 검증: 테스트 4.2 통과, 브라우저에서 시각적 확인

- [ ] **작업 4.8**: 예약 관리 페이지 구현
  - 파일: `frontend/src/pages/Reservations.tsx`
  - 목표: 예약 CRUD 및 캘린더 뷰
  - 세부사항:
    - 테이블 뷰: Ant Design Table 컴포넌트
      - 컬럼: 예약자명, 전화번호, 예약일시, 상태, 액션 (수정/삭제)
      - 검색/필터 (상태별, 날짜 범위)
      - 페이지네이션
    - 캘린더 뷰: Ant Design Calendar 또는 FullCalendar
      - 날짜별 예약 표시
      - 예약 클릭 시 상세 모달
    - 신규 예약 모달 (폼: 이름, 전화번호, 날짜, 시간, 메모)
  - 검증: 예약 생성/수정/삭제 → 백엔드 API 호출 → 목록 갱신 확인

- [ ] **작업 4.9**: SMS 모니터링 페이지 구현
  - 파일: `frontend/src/pages/Messages.tsx`
  - 목표: SMS 이력 조회 및 수동 응답
  - 세부사항:
    - SMS 이력 테이블 (발신자, 수신자, 내용, 방향, 상태, 시간)
    - 필터 (방향: 수신/발신, 상태: 성공/실패, 날짜 범위)
    - 검토 대기 큐 (Human-in-the-Loop 메시지)
    - 수동 응답 기능 (메시지 선택 → 응답 작성 → 발송)
  - 검증: 메시지 목록 표시, 수동 발송 성공

- [ ] **작업 4.10**: 룰 관리 페이지 구현
  - 파일: `frontend/src/pages/Rules.tsx`
  - 목표: 응답 룰 CRUD 인터페이스
  - 세부사항:
    - 룰 목록 테이블 (이름, 패턴, 응답 템플릿, 우선순위, 활성화 여부)
    - 룰 추가/수정 모달 (폼: 이름, 패턴, 응답, 우선순위)
    - 룰 활성화/비활성화 토글
    - 우선순위 드래그 앤 드롭 (선택)
  - 검증: 룰 생성 → 백엔드 저장 → 목록 갱신

- [ ] **작업 4.11**: 문서 관리 페이지 구현
  - 파일: `frontend/src/pages/Documents.tsx`
  - 목표: RAG 문서 업로드 및 관리
  - 세부사항:
    - 문서 목록 테이블 (파일명, 업로드 시간, 인덱싱 상태)
    - 파일 업로드 (Ant Design Upload 컴포넌트)
      - 지원 형식: PDF, TXT, XLSX
      - 업로드 진행률 표시
    - 문서 삭제 버튼
    - 인덱싱 상태 표시 (대기/진행중/완료/실패)
  - 검증: 파일 업로드 → 인덱싱 시작 → 상태 갱신 확인

**🔵 REFACTOR: 코드 품질 개선**

- [ ] **작업 4.12**: 프론트엔드 코드 리팩토링
  - 파일: 전체 Phase 4 코드
  - 목표: 테스트를 유지하며 코드 품질 향상
  - 체크리스트:
    - [ ] 공통 컴포넌트 추출 (테이블, 모달, 폼)
    - [ ] 상태 관리 개선 (Zustand 스토어 활용)
    - [ ] API 호출 로딩/에러 상태 일관성 있게 처리
    - [ ] UI/UX 개선 (로딩 스피너, 에러 토스트, 빈 상태 메시지)
    - [ ] 반응형 디자인 확인 (모바일 대응)
    - [ ] 접근성 개선 (키보드 네비게이션, ARIA 레이블)
  - 검증: 모든 테스트 여전히 통과, 사용성 향상

#### Quality Gate ✋

**⚠️ STOP: 프로젝트 완료 선언 전에 모든 체크 통과 확인**

**TDD 준수** (필수):
- [ ] **Red 단계**: 테스트를 먼저 작성했고 초기에 실패함
- [ ] **Green 단계**: 프로덕션 코드를 작성하여 테스트 통과
- [ ] **Refactor 단계**: 테스트를 유지하며 코드 개선 완료
- [ ] **컴포넌트 테스트**: 주요 컴포넌트 테스트 커버리지 확인
  ```bash
  cd frontend
  npm run test -- --coverage
  ```

**빌드 & 테스트**:
- [ ] **프론트엔드 빌드**: `npm run build` 성공
- [ ] **린트**: `npm run lint` 에러 없음
- [ ] **타입 체크**: `tsc --noEmit` 통과
- [ ] **모든 테스트 통과**: `npm run test` 100% 통과

**기능 검증**:
- [ ] **대시보드**: 모든 통계 카드 및 차트 정상 표시
- [ ] **예약 관리**:
  - 예약 목록 표시
  - 신규 예약 생성 → 목록 갱신
  - 예약 수정/삭제 정상 작동
  - 캘린더 뷰 정상 표시
- [ ] **SMS 모니터링**:
  - 이력 목록 표시
  - 검토 대기 큐 표시
  - 수동 응답 발송 성공
- [ ] **룰 관리**:
  - 룰 목록 표시
  - 룰 생성/수정/삭제 정상 작동
  - 우선순위 변경 반영
- [ ] **문서 관리**:
  - 문서 목록 표시
  - 파일 업로드 → 인덱싱 진행 확인
  - 문서 삭제 정상 작동

**E2E 테스트** (선택적이지만 권장):
- [ ] **전체 플로우**: SMS 수신 → 자동 응답 → 대시보드 이력 확인
  1. 백엔드 웹훅으로 SMS 수신 시뮬레이션
  2. 메시지 라우터가 자동 응답 생성
  3. 대시보드에서 해당 메시지 이력 확인
  4. 통계 갱신 확인

**UI/UX 품질**:
- [ ] **반응형**: 모바일 (375px), 태블릿 (768px), 데스크톱 (1920px) 모두 확인
- [ ] **로딩 상태**: 모든 API 호출 시 로딩 인디케이터 표시
- [ ] **에러 처리**: 에러 발생 시 사용자 친화적인 메시지 표시
- [ ] **빈 상태**: 데이터 없을 때 Empty 상태 표시
- [ ] **접근성**: 키보드만으로 모든 기능 사용 가능

**보안 & 성능**:
- [ ] **XSS 방지**: 사용자 입력 적절히 이스케이프
- [ ] **CORS 설정**: 백엔드 CORS 설정 확인
- [ ] **성능**: Lighthouse 점수 ≥80 (Performance)
- [ ] **번들 크기**: 초기 번들 크기 ≤1MB (gzip 압축 후)

**문서화**:
- [ ] **프론트엔드 README**: 설치 및 실행 방법 문서화
- [ ] **컴포넌트 문서**: 주요 컴포넌트 사용법 설명
- [ ] **사용자 가이드**: 대시보드 사용법 간단히 문서화 (선택)

**검증 명령**:
```bash
# 프론트엔드 빌드
cd frontend
npm run build

# 린트 및 타입 체크
npm run lint
tsc --noEmit

# 테스트 실행
npm run test -- --coverage

# 프로덕션 빌드 미리보기
npm run preview

# Lighthouse 성능 측정 (Chrome DevTools)
# 또는 CLI: npm install -g lighthouse && lighthouse http://localhost:4173
```

**수동 테스트 체크리스트**:
- [ ] 브라우저에서 각 페이지 접속 및 기능 확인
- [ ] 크롬, 파이어폭스, 사파리에서 정상 작동 확인 (주요 브라우저)
- [ ] 모바일 디바이스 (실제 또는 에뮬레이터)에서 확인
- [ ] 네트워크 느린 환경 시뮬레이션 (Chrome DevTools Throttling)

---

## ⚠️ 리스크 평가

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|-----------|
| **네이버 예약 API 제약** | 높음 | 높음 | 공식 API 제한 시 크롤링으로 대체, Selenium/Playwright 사용. 정기적 동기화 간격 조정하여 부하 분산. |
| **SMS 수신 웹훅 지원 불확실성** | 중간 | 높음 | SMS 서비스 선택 시 웹훅 지원 확인 (NHN Cloud 추천). 대체안: Polling 방식으로 메시지 조회. |
| **Google Sheets 동기화 충돌** | 중간 | 중간 | 타임스탬프 기반 충돌 해결 전략 구현. 수동 충돌 해결 UI 제공 (관리자 대시보드). |
| **RAG 응답 품질 관리** | 중간 | 중간 | 초기에는 룰 기반 응답 비중 높임 (80%), RAG는 점진적 확대 (20%). Human-in-the-Loop 큐로 애매한 응답 검토. LLM 프롬프트 지속 개선. |
| **LLM API 비용 초과** | 낮음 | 중간 | 토큰 제한 설정 (max_tokens), 캐싱 전략 적용. 월별 비용 모니터링 알림 설정. |
| **실시간 동기화 지연** | 낮음 | 낮음 | 주기적 동기화(5-10분)로 충분한지 사용자 피드백 수집. WebSocket 실시간 알림으로 UX 개선. |
| **프론트엔드 번들 크기 증가** | 낮음 | 낮음 | Code splitting 적용, lazy loading 사용. Vite의 tree shaking 활용. |

---

## 🔄 롤백 전략

### Phase 1 실패 시
**복원 단계**:
1. Docker 컨테이너 중지 및 제거: `docker-compose down -v`
2. DB 마이그레이션 롤백: `alembic downgrade base`
3. 생성된 코드 제거: `git reset --hard HEAD` (커밋 전) 또는 `git revert <commit>`
4. `.env` 파일 백업 복원

**영향**: 백엔드 기반 구조만 영향, 다른 Phase 미영향

### Phase 2 실패 시
**복원 단계**:
1. Phase 1 완료 상태로 복원
2. RAG 관련 코드 제거: `app/rag/`, `app/rules/`, `app/router/` 삭제
3. ChromaDB 데이터 삭제: `rm -rf ./chroma_data/`
4. DB 마이그레이션 롤백 (RAG 관련 테이블): `alembic downgrade -1`
5. 의존성 롤백: `requirements.txt`에서 `langchain`, `chromadb`, `anthropic` 제거 후 `pip install -r requirements.txt`

**영향**: 자동 응답 기능 제거, SMS 수신/발신은 여전히 작동

### Phase 3 실패 시
**복원 단계**:
1. Phase 2 완료 상태로 복원
2. 예약 연동 코드 제거: `app/reservation/` 삭제
3. APScheduler 작업 중지
4. Google Sheets 동기화 중단
5. DB 마이그레이션 롤백 (예약 관련 테이블): `alembic downgrade -1`

**영향**: 예약 관리 기능 제거, 자동 응답은 여전히 작동

### Phase 4 실패 시
**복원 단계**:
1. Phase 3 완료 상태로 복원
2. 프론트엔드 빌드 제거: `rm -rf frontend/dist/`
3. 백엔드만 사용 (API만 제공)
4. 필요 시 간단한 정적 HTML 페이지로 대체

**영향**: 웹 대시보드 미제공, 백엔드 API는 여전히 작동 (Swagger UI로 관리 가능)

---

## 📊 진행 상황 추적

### 완료 상태
- **Phase 1**: ⏳ 0%
- **Phase 2**: ⏳ 0%
- **Phase 3**: ⏳ 0%
- **Phase 4**: ⏳ 0%

**전체 진행률**: 0% 완료

### 시간 추적
| Phase | 예상 | 실제 | 차이 |
|-------|------|------|------|
| Phase 1 | 3시간 | - | - |
| Phase 2 | 4시간 | - | - |
| Phase 3 | 4시간 | - | - |
| Phase 4 | 4시간 | - | - |
| **전체** | 15시간 | - | - |

---

## 📝 노트 및 학습 내용

### 구현 노트
- (구현 중 발견한 인사이트를 여기에 기록)

### 발생한 블로커
- (블로커 발생 시 기록) → (해결 방법)

### 향후 개선사항
- (다음에 더 잘할 수 있는 방법 기록)

---

## 📚 참고자료

### 문서
- FastAPI 공식 문서: https://fastapi.tiangolo.com/
- LangChain 문서: https://python.langchain.com/docs/get_started/introduction
- ChromaDB 문서: https://docs.trychroma.com/
- Anthropic API 문서: https://docs.anthropic.com/
- React 공식 문서: https://react.dev/
- Ant Design 문서: https://ant.design/

### 관련 이슈
- (관련 이슈나 PR 링크)

### 기술 스택 버전
- Python: 3.10+
- FastAPI: 0.110.0
- PostgreSQL: 15
- ChromaDB: 0.4.22
- Node.js: 18+
- React: 18.2.0
- Ant Design: 5.14.0

---

## ✅ 최종 체크리스트

**프로젝트 완료 선언 전 확인사항**:
- [ ] 모든 Phase의 품질 게이트 통과
- [ ] 전체 통합 테스트 수행 완료
- [ ] E2E 테스트: SMS 수신 → 자동 응답 → 대시보드 확인 플로우 성공
- [ ] 백엔드 API 문서 완성 (Swagger UI)
- [ ] 프론트엔드 빌드 및 배포 가능 상태
- [ ] 성능 벤치마크 목표 달성
- [ ] 보안 검토 완료 (API 키 보호, XSS 방지, SQL 인젝션 방지)
- [ ] README 및 사용자 가이드 문서화
- [ ] `.env.example` 파일 완전성 확인
- [ ] Docker Compose 프로덕션 배포 준비
- [ ] 모니터링 및 로깅 설정 (선택)
- [ ] 팀원 또는 이해관계자 데모 완료
- [ ] 계획 문서 보관 및 참조 가능성 확보

---

## 📖 TDD 방법론 요약

이 프로젝트는 Test-Driven Development (TDD) 방법론을 따릅니다:

### Red-Green-Refactor 사이클

```
Phase N: 🔴 RED (실패하는 테스트 작성)
├── 무엇을 테스트할 것인가?
├── 어떤 동작이 예상되는가?
├── 테스트 작성 → 실행 → 실패 확인 ❌
└── "테스트 실패는 기능 미구현을 의미함"

Phase N: 🟢 GREEN (최소 구현으로 테스트 통과)
├── 테스트를 통과시키는 최소 코드 작성
├── 테스트 실행 → 통과 확인 ✅
└── "과도한 설계 금지, 테스트 통과가 목표"

Phase N: 🔵 REFACTOR (코드 품질 개선)
├── 중복 제거 (DRY 원칙)
├── 명명 개선
├── 구조 최적화
├── 테스트 실행 → 여전히 통과 확인 ✅
└── "테스트는 리팩토링의 안전망"

다음 기능으로 반복 →
```

### TDD의 이점
- **안전성**: 테스트가 회귀를 즉시 포착
- **설계**: 테스트가 API 설계를 먼저 고민하게 함
- **문서화**: 테스트가 예상 동작을 문서화
- **자신감**: 리팩토링 시 무너질 걱정 없음
- **품질**: 첫날부터 높은 코드 커버리지
- **디버깅**: 실패가 정확한 문제 영역을 지적

---

**계획 상태**: 🔄 진행 중
**다음 작업**: Phase 1 - 기반 구축 + SMS 연동 시작
**블로커**: 없음
