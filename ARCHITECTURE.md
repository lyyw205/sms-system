# 시스템 아키텍처

## 전체 시스템 구조

```
┌──────────────────────────────────────────────────────────────────┐
│                         사용자 (클라이언트)                        │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   웹 브라우저    │
                    │  :5173 (Vite)   │
                    └────────┬────────┘
                             │ HTTP
┌────────────────────────────▼──────────────────────────────────────┐
│                     프론트엔드 (React)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │Dashboard │  │Messages  │  │Reserv.   │  │Rules     │  ...     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       └─────────────┴─────────────┴─────────────┘                 │
│                  API Client (axios)                                │
└────────────────────────────┬──────────────────────────────────────┘
                             │ REST API
┌────────────────────────────▼──────────────────────────────────────┐
│                    백엔드 (FastAPI) :8000                          │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    API Layer (Routers)                      │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐          │  │
│  │  │Msgs │ │Resv │ │Rules│ │Docs │ │Auto │ │Dash │  ...     │  │
│  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘          │  │
│  └─────┼───────┼───────┼───────┼───────┼───────┼──────────────┘  │
│        └───────┴───────┴───────┴───────┴───────┘                  │
│                            │                                       │
│  ┌─────────────────────────▼───────────────────────────────────┐  │
│  │                 Business Logic Layer                        │  │
│  │  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │  │
│  │  │Message Router  │  │Rule Engine   │  │Reservation      │ │  │
│  │  │(Rule→LLM→Human)│  │(Regex Match) │  │Notifier (Event) │ │  │
│  │  └────────────────┘  └──────────────┘  └─────────────────┘ │  │
│  └───────────────────────────┬─────────────────────────────────┘  │
│                              │                                    │
│  ┌───────────────────────────▼─────────────────────────────────┐  │
│  │              Provider Abstraction Layer (Protocol)          │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │  │
│  │  │SMS      │  │LLM      │  │Reserv.  │  │Storage  │        │  │
│  │  │Provider │  │Provider │  │Provider │  │Provider │        │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │  │
│  └───────┼────────────┼────────────┼────────────┼──────────────┘  │
│          │            │            │            │                 │
│  ┌───────▼────────────▼────────────▼────────────▼──────────────┐  │
│  │            Factory (DEMO_MODE Switch)                       │  │
│  │  if DEMO_MODE:                                              │  │
│  │      return Mock...()  ◄── 데모 모드 (현재)                │  │
│  │  else:                                                      │  │
│  │      return Real...()  ◄── 프로덕션 모드 (계약 후)          │  │
│  └─────┬────────────┬────────────┬────────────┬────────────────┘  │
│        │            │            │            │                   │
│  ┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐ ┌───▼─────┐            │
│  │Mock       │ │Mock     │ │Mock       │ │Mock     │            │
│  │SMS        │ │LLM      │ │Reserv.    │ │Storage  │            │
│  │(Log출력)  │ │(키워드) │ │(JSON)     │ │(CSV)    │            │
│  └───────────┘ └─────────┘ └───────────┘ └─────────┘            │
│                                                                   │
│  ┌───────────┐ ┌─────────┐ ┌───────────┐ ┌─────────┐            │
│  │Real       │ │Real     │ │Real       │ │Real     │            │
│  │SMS        │ │LLM      │ │Reserv.    │ │Storage  │            │
│  │(NHN Cloud)│ │(Claude) │ │(Naver API)│ │(Sheets) │ (스텁)     │
│  └───────────┘ └─────────┘ └───────────┘ └─────────┘            │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                      Data Access Layer                       │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │ │
│  │  │SQLAlchemy   │  │Redis        │  │ChromaDB     │          │ │
│  │  │Models & ORM │  │(Cache/Queue)│  │(RAG Vector) │          │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │ │
│  └─────────┼─────────────────┼─────────────────┼────────────────┘ │
└────────────┼─────────────────┼─────────────────┼──────────────────┘
             │                 │                 │
┌────────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
│   PostgreSQL        │ │   Redis     │ │   ChromaDB      │
│  (Messages, Resv.,  │ │  (캐시/큐)  │ │  (RAG 임베딩)   │
│   Rules, Docs)      │ │             │ │                 │
│   :5432             │ │   :6379     │ │   :8001         │
└─────────────────────┘ └─────────────┘ └─────────────────┘
```

## 메시지 처리 플로우 (자동 응답)

```
┌─────────────┐
│ SMS 수신    │
│ (고객)      │
└──────┬──────┘
       │
       │ 1. SMS 도착
       ▼
┌─────────────────────┐
│ SMS Provider        │
│ (Mock: 시뮬레이터)  │  ◄── 프론트엔드 시뮬레이터 트리거
│ (Real: NHN 웹훅)    │
└──────┬──────────────┘
       │
       │ 2. DB 저장
       ▼
┌─────────────────────┐
│ Message Model       │
│ (SQLAlchemy)        │
│ - direction: inbound│
│ - status: received  │
└──────┬──────────────┘
       │
       │ 3. 자동 응답 생성
       ▼
┌─────────────────────────────────────────┐
│ Message Router                          │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ 1단계: 룰 엔진 시도               │  │
│  │  - 정규식 패턴 매칭               │  │
│  │  - 우선순위 정렬                  │  │
│  │  - Confidence: 0.95               │  │
│  └────────┬──────────────────────────┘  │
│           │ 매칭 성공?                  │
│           │ Yes ──────┐                 │
│           │ No        │                 │
│           ▼           │                 │
│  ┌───────────────┐    │                 │
│  │ 2단계: LLM    │    │                 │
│  │ (Mock: 키워드)│    │                 │
│  │ (Real: Claude)│    │                 │
│  │ Conf: 0.3-0.9 │    │                 │
│  └────┬──────────┘    │                 │
│       │               │                 │
│       └───────────────┘                 │
│              │                          │
│              ▼                          │
│  ┌─────────────────────────────────┐   │
│  │ 3단계: 신뢰도 체크              │   │
│  │  - Confidence >= 0.6?           │   │
│  │    Yes → 자동 발송              │   │
│  │    No  → Human-in-the-Loop      │   │
│  └────────┬────────────────────────┘   │
└───────────┼──────────────────────────────┘
            │
    ┌───────▼───────┐
    │ Conf >= 0.6?  │
    └───┬───────┬───┘
        │ Yes   │ No
        │       │
        │       ▼
        │  ┌────────────────────┐
        │  │ Review Queue       │
        │  │ (needs_review=true)│
        │  │ → 검토 대기 탭     │
        │  └────────────────────┘
        │
        ▼
┌────────────────────┐
│ SMS 자동 발송      │
│ (SMS Provider)     │
└─────────┬──────────┘
          │
          ▼
    ┌──────────┐
    │ 고객 수신│
    └──────────┘
```

## 예약 상태 변경 플로우

```
┌─────────────────┐
│ 예약 생성/수정  │
│ (프론트엔드)    │
└────────┬────────┘
         │
         │ POST /api/reservations
         ▼
┌──────────────────────────┐
│ Reservation API          │
│ (reservations.py)        │
└────────┬─────────────────┘
         │
         │ SQLAlchemy ORM
         ▼
┌──────────────────────────────────────┐
│ Reservation Model                    │
│  - id, customer_name, phone, ...     │
│  - status: pending/confirmed/...     │
└────────┬─────────────────────────────┘
         │
         │ SQLAlchemy Event Listener
         │ @event.listens_for(Reservation, "after_insert")
         │ @event.listens_for(Reservation, "after_update")
         ▼
┌──────────────────────────────────────┐
│ Reservation Notifier                 │
│ (notifier.py)                        │
│                                      │
│  1. 상태 확인                        │
│  2. SMS 템플릿 선택                  │
│     - pending:   "예약 접수"         │
│     - confirmed: "예약 확정"         │
│     - cancelled: "예약 취소"         │
│  3. SMS 발송                         │
└────────┬─────────────────────────────┘
         │
         │ send_sms_sync()
         ▼
┌──────────────────────┐
│ SMS Provider         │
│ (Mock 또는 Real)     │
└────────┬─────────────┘
         │
         ▼
┌──────────────┐
│ 고객에게 SMS │
│ 알림 발송    │
└──────────────┘
```

## 네이버 예약 동기화 플로우

```
┌─────────────────────┐
│ "네이버 동기화" 버튼│
│ (프론트엔드)        │
└──────────┬──────────┘
           │
           │ POST /api/reservations/sync/naver
           ▼
┌───────────────────────────────────┐
│ Reservation API                   │
│ (sync_from_naver endpoint)        │
└──────────┬────────────────────────┘
           │
           │ get_reservation_provider()
           ▼
┌───────────────────────────────────┐
│ Provider Factory                  │
│  if DEMO_MODE:                    │
│      MockReservationProvider()    │
│  else:                            │
│      RealReservationProvider()    │
└──────────┬────────────────────────┘
           │
    ┌──────▼──────┐
    │ DEMO_MODE?  │
    └──┬───────┬──┘
       │ True  │ False
       │       │
       ▼       ▼
┌─────────┐  ┌────────────────┐
│Mock     │  │Real            │
│Provider │  │Provider        │
│         │  │                │
│JSON파일 │  │Naver API       │
│읽기     │  │또는 크롤링     │
└────┬────┘  └────┬───────────┘
     │            │
     └─────┬──────┘
           │ 예약 리스트 반환
           ▼
┌───────────────────────────────────┐
│ 예약 데이터 처리                  │
│  1. 중복 체크 (external_id)       │
│  2. 신규 예약만 DB 저장           │
│  3. 예약 저장 시 이벤트 트리거    │
│     → SMS 알림 자동 발송          │
└──────────┬────────────────────────┘
           │
           ▼
┌─────────────────┐
│ 응답 반환       │
│ {synced: N,     │
│  added: M}      │
└─────────────────┘
```

## Google Sheets 동기화 플로우

```
┌────────────────────┐
│ "Sheets 동기화" 버튼│
│ (프론트엔드)       │
└──────────┬─────────┘
           │
           │ POST /api/reservations/sync/sheets
           ▼
┌───────────────────────────────────┐
│ Reservation API                   │
│ (sync_to_google_sheets endpoint)  │
│  1. DB에서 모든 예약 조회         │
│  2. Dict 형태로 변환              │
└──────────┬────────────────────────┘
           │
           │ get_storage_provider()
           ▼
┌───────────────────────────────────┐
│ Provider Factory                  │
│  if DEMO_MODE:                    │
│      MockStorageProvider()        │
│  else:                            │
│      RealStorageProvider()        │
└──────────┬────────────────────────┘
           │
    ┌──────▼──────┐
    │ DEMO_MODE?  │
    └──┬───────┬──┘
       │ True  │ False
       │       │
       ▼       ▼
┌─────────┐  ┌────────────────┐
│Mock     │  │Real            │
│Provider │  │Provider        │
│         │  │                │
│CSV 파일 │  │Google Sheets   │
│저장     │  │API 호출        │
│         │  │(gspread)       │
└────┬────┘  └────┬───────────┘
     │            │
     └─────┬──────┘
           │
           ▼
┌─────────────────────────┐
│ Mock: CSV 파일 생성     │
│ app/mock/data/          │
│   reservations.csv      │
│                         │
│ Real: Google Sheets     │
│ 스프레드시트 업데이트   │
└─────────────────────────┘
```

## 핫스왑 메커니즘 (DEMO_MODE Switch)

```
┌──────────────────────────────────────────┐
│ .env 파일                                │
│                                          │
│ DEMO_MODE=true   ◄── 환경변수 변경만!   │
│                                          │
│ # 프로덕션 모드로 전환:                  │
│ # DEMO_MODE=false                        │
│ # SMS_API_KEY=...                        │
│ # CLAUDE_API_KEY=...                     │
└──────────────┬───────────────────────────┘
               │
               │ Pydantic Settings
               ▼
┌──────────────────────────────────────────┐
│ config.py                                │
│                                          │
│ class Settings(BaseSettings):           │
│     DEMO_MODE: bool = True               │
│     SMS_API_KEY: str = ""                │
│     ...                                  │
│                                          │
│ settings = Settings()  ◄── 싱글톤        │
└──────────────┬───────────────────────────┘
               │
               │ settings.DEMO_MODE
               ▼
┌──────────────────────────────────────────┐
│ factory.py (Provider Factory)            │
│                                          │
│ def get_sms_provider():                  │
│     if settings.DEMO_MODE:               │
│         return MockSMSProvider()         │
│     else:                                │
│         return RealSMSProvider(          │
│             api_key=settings.SMS_API_KEY │
│         )                                │
│                                          │
│ def get_llm_provider():                  │
│     if settings.DEMO_MODE:               │
│         return MockLLMProvider()         │
│     else:                                │
│         return RealLLMProvider(          │
│             api_key=settings.CLAUDE_API_KEY│
│         )                                │
│                                          │
│ ... (reservation, storage)               │
└──────────────┬───────────────────────────┘
               │
    ┌──────────▼──────────┐
    │ API 엔드포인트에서  │
    │ Factory 함수 호출   │
    └──────────┬──────────┘
               │
        ┌──────▼─────┐
        │ DEMO_MODE? │
        └──┬────────┬─┘
           │ True   │ False
           │        │
           ▼        ▼
    ┌───────────┐  ┌────────────┐
    │ Mock 구현 │  │ Real 구현  │
    │           │  │            │
    │ - 로그    │  │ - 실제 API │
    │ - 파일    │  │ - 외부 연동│
    │ - 키워드  │  │ - Claude   │
    │           │  │ - 웹훅     │
    └───────────┘  └────────────┘
```

## 데이터베이스 스키마

```
┌─────────────────────────┐
│ messages                │
├─────────────────────────┤
│ id (PK)                 │
│ message_id (UNIQUE)     │
│ direction (ENUM)        │ ◄── inbound/outbound
│   - inbound             │
│   - outbound            │
│ from_phone              │
│ to                      │
│ message (TEXT)          │
│ status (ENUM)           │ ◄── pending/sent/failed/received
│ auto_response (TEXT)    │ ◄── 생성된 자동 응답
│ auto_response_confidence│ ◄── 신뢰도 (0-1)
│ needs_review (BOOL)     │ ◄── Human-in-the-Loop 플래그
│ response_source         │ ◄── rule/llm/manual
│ created_at              │
└─────────────────────────┘
            │
            │ 1:N (전화번호로 연결)
            │
┌─────────────────────────┐
│ reservations            │
├─────────────────────────┤
│ id (PK)                 │
│ external_id (UNIQUE)    │ ◄── 네이버 예약 ID
│ customer_name           │
│ phone                   │
│ date                    │
│ time                    │
│ status (ENUM)           │ ◄── pending/confirmed/cancelled/completed
│   - pending             │     ▲
│   - confirmed           │     │ Event Listener
│   - cancelled           │     │ → SMS 알림 자동 발송
│   - completed           │     │
│ notes (TEXT)            │
│ source                  │ ◄── naver/manual/phone
│ created_at              │
│ updated_at              │
└─────────────────────────┘

┌─────────────────────────┐
│ rules                   │
├─────────────────────────┤
│ id (PK)                 │
│ name                    │
│ pattern (REGEX)         │ ◄── 정규식 패턴
│ response (TEXT)         │ ◄── 자동 응답 텍스트
│ priority (INT)          │ ◄── 우선순위 (높을수록 우선)
│ active (BOOL)           │
│ created_at              │
│ updated_at              │
└─────────────────────────┘

┌─────────────────────────┐
│ documents               │
├─────────────────────────┤
│ id (PK)                 │
│ filename                │
│ content (TEXT)          │
│ file_path               │
│ uploaded_at             │
│ indexed (BOOL)          │ ◄── ChromaDB 인덱싱 완료 여부
└─────────────────────────┘
            │
            │ 인덱싱 시
            ▼
┌─────────────────────────┐
│ ChromaDB                │
│ (Vector Database)       │
│                         │
│ - Embeddings            │
│ - Similarity Search     │
│ - RAG Context           │
└─────────────────────────┘
```

## API 레이어 구조

```
FastAPI App (:8000)
│
├─ /api/messages
│   ├─ GET  /                    → 메시지 목록
│   ├─ POST /send                → 수동 SMS 발송
│   └─ GET  /review-queue        → 검토 대기 메시지
│
├─ /api/reservations
│   ├─ GET    /                  → 예약 목록
│   ├─ POST   /                  → 예약 생성
│   ├─ PUT    /{id}              → 예약 수정
│   ├─ DELETE /{id}              → 예약 삭제
│   ├─ POST   /sync/naver        → 네이버 동기화
│   └─ POST   /sync/sheets       → Google Sheets 동기화
│
├─ /api/rules
│   ├─ GET    /                  → 룰 목록
│   ├─ POST   /                  → 룰 생성
│   ├─ PUT    /{id}              → 룰 수정
│   └─ DELETE /{id}              → 룰 삭제
│
├─ /api/documents
│   ├─ GET    /                  → 문서 목록
│   ├─ POST   /upload            → 문서 업로드
│   └─ DELETE /{id}              → 문서 삭제
│
├─ /api/auto-response
│   ├─ POST /generate            → 자동 응답 생성 (메시지 ID)
│   ├─ POST /test                → 응답 테스트 (텍스트)
│   └─ POST /reload-rules        → 룰 핫 리로드
│
├─ /api/dashboard
│   └─ GET  /stats               → 대시보드 통계
│
└─ /webhooks
    └─ POST /sms/receive         → SMS 수신 웹훅
```

## 프론트엔드 컴포넌트 트리

```
App.tsx
│
├─ Router (React Router)
│   │
│   └─ Layout.tsx
│       │
│       ├─ Sider (메뉴)
│       │   ├─ Dashboard
│       │   ├─ Reservations
│       │   ├─ Messages
│       │   ├─ Rules
│       │   └─ Documents
│       │
│       ├─ Header
│       │   └─ "SMS 예약 시스템 - Demo Mode"
│       │
│       └─ Content (페이지 렌더링)
│           │
│           ├─ Dashboard.tsx
│           │   ├─ Statistic Cards (3개)
│           │   ├─ PieChart (Recharts)
│           │   └─ Tables (최근 예약/메시지)
│           │
│           ├─ Reservations.tsx
│           │   ├─ Action Buttons
│           │   │   ├─ 신규 예약
│           │   │   ├─ 네이버 동기화
│           │   │   └─ Google Sheets 동기화
│           │   ├─ Table (예약 목록)
│           │   └─ Modal (예약 CRUD)
│           │
│           ├─ Messages.tsx
│           │   ├─ SMSSimulator.tsx
│           │   │   ├─ Input (발신자 번호)
│           │   │   ├─ TextArea (메시지)
│           │   │   ├─ Quick Buttons
│           │   │   └─ Submit Button
│           │   │
│           │   └─ Tabs
│           │       ├─ 전체 메시지 (Table)
│           │       └─ 검토 대기 (Table + Actions)
│           │
│           ├─ Rules.tsx
│           │   ├─ Action Button (룰 추가)
│           │   ├─ Table (룰 목록)
│           │   └─ Modal (룰 CRUD)
│           │
│           └─ Documents.tsx
│               ├─ Upload Button (Ant Design)
│               └─ Table (문서 목록)
```

## 배포 아키텍처 (프로덕션)

```
                    ┌──────────────┐
                    │   사용자     │
                    └──────┬───────┘
                           │ HTTPS
                    ┌──────▼───────┐
                    │ Load Balancer│
                    │ (Nginx/ALB)  │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌────────▼──────┐  ┌───────▼──────┐
│ 프론트엔드    │  │ 프론트엔드     │  │ 프론트엔드    │
│ (React)      │  │ (React)       │  │ (React)      │
│ :5173 (dev)  │  │ Static Files  │  │ Static Files │
└──────────────┘  └───────────────┘  └──────────────┘
                           │
                    ┌──────▼───────┐
                    │ API Gateway  │
                    │ (FastAPI)    │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌────────▼──────┐  ┌───────▼──────┐
│ FastAPI      │  │ FastAPI       │  │ FastAPI      │
│ Instance 1   │  │ Instance 2    │  │ Instance 3   │
│ :8000        │  │ :8000         │  │ :8000        │
└──────┬───────┘  └───────┬───────┘  └──────┬───────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼──────┐  ┌───────▼──────┐  ┌──────▼───────┐
│ PostgreSQL   │  │ Redis        │  │ ChromaDB     │
│ (Primary +   │  │ (Cache/Queue)│  │ (RAG Vector) │
│  Replica)    │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

**이 아키텍처는 Demo Mode와 Production Mode를 환경변수만으로 전환 가능한 핫스왑 구조를 제공합니다.**
