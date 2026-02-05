# 빠른 시작 가이드 (5분)

Docker 없이 빠르게 시스템을 테스트할 수 있는 가이드입니다.

## 1단계: 의존성 설치 (2분)

### 백엔드

```bash
cd backend

# Python 가상환경 생성
python -m venv venv

# 활성화
# Linux/Mac:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 프론트엔드

```bash
cd frontend

# 의존성 설치
npm install
```

## 2단계: 환경 설정 (1분)

```bash
cd backend

# .env 파일 생성
cp .env.example .env

# .env 내용 (이미 기본값으로 설정됨):
# DEMO_MODE=true
# DATABASE_URL=postgresql://smsuser:smspass@localhost:5432/smsdb
```

## 3단계: 데이터베이스 (옵션)

### Option A: SQLite 사용 (Docker 없이)

```bash
# backend/.env 수정
DATABASE_URL=sqlite:///./sms.db

# 시드 데이터 생성
cd backend
python -m app.db.seed
```

### Option B: Docker 사용 (권장)

```bash
# 프로젝트 루트에서
docker compose up -d postgres

# 시드 데이터 생성
cd backend
python -m app.db.seed
```

## 4단계: 서버 실행 (1분)

### 터미널 1: 백엔드

```bash
cd backend
source venv/bin/activate  # 또는 Windows: venv\Scripts\activate
uvicorn app.main:app --reload
```

✅ 백엔드 실행: http://localhost:8000
✅ Swagger UI: http://localhost:8000/docs

### 터미널 2: 프론트엔드

```bash
cd frontend
npm run dev
```

✅ 프론트엔드 실행: http://localhost:5173

## 5단계: 시연 (1분)

1. **브라우저에서 http://localhost:5173 접속**

2. **SMS 수신 시뮬레이션**:
   - Messages 페이지로 이동
   - 발신자: `010-1234-5678`
   - 메시지: `영업시간이 어떻게 되나요?`
   - "수신 시뮬레이션" 클릭

3. **터미널 로그 확인**:
   ```
   📥 [MOCK SMS RECEIVED]
      From: 010-1234-5678
      Message: 영업시간이 어떻게 되나요?

   📤 [MOCK SMS SENT]
      To: 010-1234-5678
      Message: 평일 09:00-18:00, 주말 10:00-17:00 영업합니다.
   ```

4. **대시보드 확인**: Dashboard 페이지에서 통계 확인

## 🎯 주요 API 테스트 (Swagger UI 사용)

http://localhost:8000/docs 접속 후:

### 1. 메시지 목록 조회
- `GET /api/messages`
- "Try it out" → "Execute"

### 2. SMS 수신 시뮬레이션
- `POST /webhooks/sms/receive`
- Request body:
  ```json
  {
    "from_": "010-1234-5678",
    "to": "010-9999-0000",
    "message": "가격이 얼마인가요?"
  }
  ```

### 3. 자동 응답 테스트
- `POST /api/auto-response/test`
- Request body:
  ```json
  {
    "message": "주차 가능한가요?"
  }
  ```

### 4. 예약 생성
- `POST /api/reservations`
- Request body:
  ```json
  {
    "customer_name": "홍길동",
    "phone": "010-9999-1111",
    "date": "2026-02-15",
    "time": "14:00",
    "status": "pending",
    "notes": "테스트 예약"
  }
  ```

### 5. 대시보드 통계
- `GET /api/dashboard/stats`
- "Try it out" → "Execute"

## 🐛 트러블슈팅

### "ModuleNotFoundError: No module named 'app'"
```bash
# backend 디렉토리에서 실행했는지 확인
cd backend
python -m app.db.seed
```

### "Cannot connect to database"
```bash
# SQLite 모드로 전환 (.env 수정)
DATABASE_URL=sqlite:///./sms.db

# 또는 Docker PostgreSQL 실행
docker compose up -d postgres
```

### "Port 8000 already in use"
```bash
# 포트 변경
uvicorn app.main:app --reload --port 8001

# 프론트엔드 vite.config.ts도 수정:
# target: 'http://localhost:8001'
```

### "npm install 실패"
```bash
# Node.js 버전 확인 (18 이상 권장)
node --version

# npm 캐시 클리어
npm cache clean --force
npm install
```

## 📝 다음 단계

1. **시연 시나리오 연습**: [README.md](./README.md#클라이언트-시연-시나리오-10분) 참고
2. **코드 이해**: [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md) 참고
3. **프로덕션 전환**: [PRODUCTION_TRANSITION_GUIDE.md](./PRODUCTION_TRANSITION_GUIDE.md) 참고

## 🎉 축하합니다!

SMS 예약 시스템이 정상적으로 실행되었습니다.

- 대시보드: http://localhost:5173
- API 문서: http://localhost:8000/docs
- 터미널에서 Mock 로그 확인

이제 클라이언트에게 시연할 준비가 완료되었습니다! 🚀
