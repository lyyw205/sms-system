# 프로덕션 전환 가이드 (9시간)

계약 체결 후 데모 시스템을 프로덕션 환경으로 전환하는 상세 가이드

## 📋 사전 준비 (계약 전)

### API 키 및 계정 준비
- [ ] **NHN Cloud SMS**: 회원가입, 프로젝트 생성, AppKey 발급
- [ ] **Claude API**: Anthropic Console에서 API 키 발급
- [ ] **Google Sheets**: 서비스 계정 생성 및 credentials.json 다운로드
- [ ] **네이버 예약**: 사업자 계정 및 예약 시스템 접근 권한 확인

### 인프라 준비
- [ ] 프로덕션 서버 (AWS EC2, GCP VM 등)
- [ ] 도메인 및 SSL 인증서
- [ ] 웹훅용 공인 IP 또는 도메인

---

## 🚀 전환 작업 (총 9시간)

### Phase 1: SMS API 연동 (1시간)

**목표**: Mock SMS → NHN Cloud SMS API 전환

#### 1.1 NHN Cloud 설정 (20분)
```bash
# 1. NHN Cloud Console 접속
# 2. SMS 서비스 활성화
# 3. 발신번호 등록 (사업자 인증 필요)
# 4. AppKey, SecretKey 확인
```

#### 1.2 RealSMSProvider 구현 (30분)
**파일**: `backend/app/real/sms.py`

```python
import httpx
import hashlib
import hmac
import base64
import time
from typing import Dict, Any


class RealSMSProvider:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api-sms.cloud.toast.com"

    async def send_sms(self, to: str, message: str, **kwargs) -> Dict[str, Any]:
        """NHN Cloud SMS API 호출"""
        url = f"{self.base_url}/sms/v2.4/appKeys/{self.api_key}/sender/sms"

        # 인증 헤더 생성
        timestamp = str(int(time.time() * 1000))
        signature = self._create_signature(timestamp)

        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Secret-Key": self.api_secret,
        }

        body = {
            "body": message,
            "sendNo": "01099990000",  # 발신번호 (사전 등록 필요)
            "recipientList": [{"recipientNo": to.replace("-", "")}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=body)
            result = response.json()

        return {
            "status": "sent" if response.status_code == 200 else "failed",
            "message_id": result.get("header", {}).get("requestId", ""),
            "to": to,
            "message": message,
            "timestamp": timestamp,
            "provider": "nhn_cloud",
        }

    def _create_signature(self, timestamp: str) -> str:
        """HMAC 서명 생성"""
        message = f"{timestamp}\n{self.api_key}"
        signature = hmac.new(
            self.api_secret.encode(), message.encode(), hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode()
```

#### 1.3 웹훅 설정 (10분)
```python
# backend/app/api/webhooks.py 수정
@router.post("/sms/receive")
async def receive_sms_webhook(request: Request, db: Session = Depends(get_db)):
    """
    NHN Cloud SMS 수신 웹훅
    설정: NHN Console > SMS > 웹훅 설정 > 수신 웹훅 URL 등록
    """
    data = await request.json()

    # NHN Cloud 웹훅 포맷 파싱
    for message in data.get("messages", []):
        msg = Message(
            message_id=message["messageId"],
            direction=MessageDirection.INBOUND,
            from_=message["from"],
            to=message["to"],
            message=message["body"],
            status=MessageStatus.RECEIVED,
        )
        db.add(msg)

    db.commit()
    return {"status": "success"}
```

#### 1.4 테스트 (5분)
```bash
# .env 수정
DEMO_MODE=false
SMS_API_KEY=your_nhn_cloud_appkey
SMS_API_SECRET=your_nhn_cloud_secret

# 서버 재시작
uvicorn app.main:app --reload

# 테스트 SMS 발송
curl -X POST http://localhost:8000/api/messages/send \
  -H "Content-Type: application/json" \
  -d '{"to": "010-1234-5678", "message": "테스트 메시지"}'
```

---

### Phase 2: 네이버 예약 연동 (2시간)

**목표**: Mock JSON → 네이버 예약 실시간 동기화

#### 2.1 네이버 예약 API 확인 (30분)
1. 네이버 예약 관리자 페이지 접속
2. API 제공 여부 확인
3. 제공되지 않으면 → Playwright 크롤링 방식 선택

#### 2.2 RealReservationProvider 구현 (1시간)

**Option A: API 제공 시**
```python
import httpx
from typing import List, Dict, Any


class RealReservationProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.booking.naver.com"  # 가상 URL

    async def sync_reservations(self) -> List[Dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/reservations", headers=headers
            )
            data = response.json()

        return [
            {
                "external_id": res["id"],
                "customer_name": res["customerName"],
                "phone": res["phone"],
                "date": res["date"],
                "time": res["time"],
                "status": res["status"],
                "notes": res.get("notes", ""),
                "source": "naver",
            }
            for res in data.get("reservations", [])
        ]
```

**Option B: 크롤링 방식 (API 미제공 시)**
```python
from playwright.async_api import async_playwright
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RealReservationProvider:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    async def sync_reservations(self) -> List[Dict[str, Any]]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 1. 로그인
            await page.goto("https://booking.naver.com/login")
            await page.fill('input[name="id"]', self.email)
            await page.fill('input[name="password"]', self.password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")

            # 2. 예약 목록 페이지 이동
            await page.goto("https://booking.naver.com/admin/reservations")
            await page.wait_for_selector(".reservation-list")

            # 3. 예약 데이터 파싱
            reservations = await page.eval_on_selector_all(
                ".reservation-item",
                """(elements) => elements.map(el => ({
                    id: el.getAttribute('data-id'),
                    customerName: el.querySelector('.customer-name').innerText,
                    phone: el.querySelector('.phone').innerText,
                    date: el.querySelector('.date').innerText,
                    time: el.querySelector('.time').innerText,
                    status: el.querySelector('.status').innerText,
                }))""",
            )

            await browser.close()

            return [
                {
                    "external_id": f"naver_{res['id']}",
                    "customer_name": res["customerName"],
                    "phone": res["phone"],
                    "date": res["date"],
                    "time": res["time"],
                    "status": self._map_status(res["status"]),
                    "notes": f"네이버 예약 - {res['id']}",
                    "source": "naver",
                }
                for res in reservations
            ]

    def _map_status(self, naver_status: str) -> str:
        """네이버 상태 → 내부 상태 매핑"""
        mapping = {
            "예약대기": "pending",
            "예약확정": "confirmed",
            "예약취소": "cancelled",
            "방문완료": "completed",
        }
        return mapping.get(naver_status, "pending")
```

#### 2.3 크롤링 의존성 추가 (크롤링 방식 선택 시)
```bash
pip install playwright
playwright install chromium
```

#### 2.4 테스트 (30분)
```bash
# .env 수정
NAVER_RESERVATION_EMAIL=your_email
NAVER_RESERVATION_PASSWORD=your_password

# 동기화 테스트
curl -X POST http://localhost:8000/api/reservations/sync/naver
```

---

### Phase 3: Google Sheets 연동 (1시간)

**목표**: Mock CSV → Google Sheets API 실시간 동기화

#### 3.1 Google Cloud 서비스 계정 생성 (20분)
1. Google Cloud Console 접속
2. 새 프로젝트 생성
3. Google Sheets API 활성화
4. 서비스 계정 생성 → credentials.json 다운로드
5. Google Sheets 파일 생성 후 서비스 계정 이메일에 편집 권한 부여

#### 3.2 RealStorageProvider 구현 (30min)
```python
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RealStorageProvider:
    def __init__(self, credentials_path: str):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            credentials_path, scope
        )
        self.client = gspread.authorize(creds)

    async def sync_to_storage(self, data: List[Dict[str, Any]], sheet_name: str) -> bool:
        try:
            # 스프레드시트 열기 (이름으로)
            spreadsheet = self.client.open("SMS 예약 시스템")
            worksheet = spreadsheet.worksheet(sheet_name)

            # 기존 데이터 삭제
            worksheet.clear()

            # 헤더 작성
            if data:
                headers = list(data[0].keys())
                worksheet.append_row(headers)

                # 데이터 작성
                for record in data:
                    row = [str(record.get(key, "")) for key in headers]
                    worksheet.append_row(row)

            logger.info(f"✅ Google Sheets 동기화 완료: {len(data)}건")
            return True
        except Exception as e:
            logger.error(f"❌ Google Sheets 동기화 실패: {e}")
            return False

    async def sync_from_storage(self, sheet_name: str) -> List[Dict[str, Any]]:
        try:
            spreadsheet = self.client.open("SMS 예약 시스템")
            worksheet = spreadsheet.worksheet(sheet_name)

            # 모든 데이터 읽기 (dict 형태)
            records = worksheet.get_all_records()
            logger.info(f"✅ Google Sheets 읽기 완료: {len(records)}건")
            return records
        except Exception as e:
            logger.error(f"❌ Google Sheets 읽기 실패: {e}")
            return []
```

#### 3.3 의존성 추가
```bash
pip install gspread oauth2client
```

#### 3.4 테스트 (10min)
```bash
# .env 수정
GOOGLE_SHEETS_CREDENTIALS=/path/to/credentials.json

# 동기화 테스트
curl -X POST http://localhost:8000/api/reservations/sync/sheets
```

---

### Phase 4: Claude API + RAG (3시간)

**목표**: Mock 키워드 매칭 → Claude API + ChromaDB RAG

#### 4.1 ChromaDB 인덱싱 (1시간)
```python
# backend/app/services/rag.py
import chromadb
from chromadb.config import Settings
from typing import List
import logging

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, chromadb_url: str):
        self.client = chromadb.HttpClient(host=chromadb_url)
        self.collection = self.client.get_or_create_collection("knowledge_base")

    def index_document(self, doc_id: str, content: str, metadata: dict):
        """문서를 ChromaDB에 인덱싱"""
        self.collection.add(
            documents=[content], metadatas=[metadata], ids=[doc_id]
        )
        logger.info(f"✅ 문서 인덱싱 완료: {doc_id}")

    def search(self, query: str, top_k: int = 3) -> List[str]:
        """관련 문서 검색"""
        results = self.collection.query(query_texts=[query], n_results=top_k)
        return results["documents"][0] if results["documents"] else []
```

#### 4.2 RealLLMProvider 구현 (1.5시간)
```python
from anthropic import Anthropic
from typing import Dict, Any, Optional
from app.services.rag import RAGService
import logging

logger = logging.getLogger(__name__)


class RealLLMProvider:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.rag = RAGService(chromadb_url="http://localhost:8001")

    async def generate_response(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Claude API + RAG로 응답 생성"""

        # 1. RAG: 관련 문서 검색
        relevant_docs = self.rag.search(message, top_k=3)
        context_text = "\n\n".join(relevant_docs) if relevant_docs else ""

        # 2. Prompt 구성
        system_prompt = f"""당신은 고객 문의에 친절하게 응답하는 AI 어시스턴트입니다.

다음은 비즈니스 관련 참고 문서입니다:
{context_text}

위 정보를 바탕으로 고객 문의에 정확하고 친절하게 답변하세요.
정보가 불충분하면 "정확한 답변을 위해 고객센터(010-9999-0000)로 연락 주세요"라고 안내하세요."""

        # 3. Claude API 호출
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": message}],
        )

        answer = response.content[0].text

        # 4. 신뢰도 계산 (휴리스틱)
        confidence = self._calculate_confidence(answer, relevant_docs)

        logger.info(
            f"🤖 Claude API 응답 생성\n"
            f"   Query: {message}\n"
            f"   Response: {answer[:100]}...\n"
            f"   Confidence: {confidence:.2f}"
        )

        return {
            "response": answer,
            "confidence": confidence,
            "needs_review": confidence < 0.6,
            "source": "llm",
        }

    def _calculate_confidence(self, answer: str, relevant_docs: List[str]) -> float:
        """신뢰도 계산 (간단한 휴리스틱)"""
        # 관련 문서가 많을수록 높은 신뢰도
        if not relevant_docs:
            return 0.4

        # "고객센터로 연락" 등의 회피 답변은 낮은 신뢰도
        if "고객센터" in answer or "연락 주세요" in answer:
            return 0.5

        # 답변 길이 기반 (너무 짧으면 낮은 신뢰도)
        if len(answer) < 20:
            return 0.45

        # 기본 신뢰도
        base_confidence = 0.75 + (len(relevant_docs) * 0.05)
        return min(base_confidence, 0.95)
```

#### 4.3 문서 업로드 시 자동 인덱싱 (30min)
```python
# backend/app/api/documents.py 수정
from app.services.rag import RAGService
from app.config import settings

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    content_text = content.decode("utf-8", errors="ignore")

    # DB 저장
    doc = Document(
        filename=file.filename,
        content=content_text,
        file_path=f"/uploads/{file.filename}",
        indexed=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # ChromaDB 인덱싱 (DEMO_MODE=false일 때만)
    if not settings.DEMO_MODE:
        rag = RAGService(settings.CHROMADB_URL)
        rag.index_document(
            doc_id=f"doc_{doc.id}",
            content=content_text,
            metadata={"filename": file.filename, "doc_id": doc.id},
        )
        doc.indexed = True
        db.commit()

    return {"status": "success", "document_id": doc.id, "indexed": doc.indexed}
```

#### 4.4 테스트 (30min)
```bash
# .env 수정
CLAUDE_API_KEY=sk-ant-...

# 1. 문서 업로드 (자동 인덱싱)
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@FAQ.txt"

# 2. 자동 응답 테스트
curl -X POST http://localhost:8000/api/auto-response/test \
  -H "Content-Type: application/json" \
  -d '{"message": "환불 정책이 어떻게 되나요?"}'
```

---

### Phase 5: 통합 테스트 (2시간)

#### 5.1 E2E 테스트 시나리오 (1시간)

**시나리오 1: SMS 수신 → 자동 응답**
1. 실제 휴대폰에서 등록된 발신번호로 SMS 발송
2. 웹훅 수신 확인 (로그 체크)
3. 자동 응답 생성 확인 (룰 또는 LLM)
4. 자동 답장 SMS 수신 확인

**시나리오 2: 예약 생성 → SMS 알림**
1. 프론트엔드에서 예약 생성
2. DB 저장 확인
3. SMS 알림 발송 로그 확인
4. 실제 SMS 수신 확인

**시나리오 3: 네이버 예약 동기화**
1. 네이버 예약 시스템에서 테스트 예약 생성
2. API 또는 크롤링으로 동기화
3. DB 반영 확인
4. SMS 알림 발송 확인

**시나리오 4: Google Sheets 동기화**
1. 예약 데이터 여러 건 생성
2. "Google Sheets 동기화" 버튼 클릭
3. Google Sheets에서 데이터 확인

#### 5.2 부하 테스트 (30min)
```bash
# Apache Bench로 간단한 부하 테스트
ab -n 1000 -c 10 http://localhost:8000/api/dashboard/stats
```

#### 5.3 에러 핸들링 확인 (30min)
- API 키 잘못 입력 시 에러 메시지 확인
- 네트워크 장애 시 재시도 로직
- 외부 API 타임아웃 처리

---

## ✅ 전환 완료 체크리스트

### 환경 설정
- [ ] `.env` 파일 모든 API 키 입력
- [ ] `DEMO_MODE=false` 설정
- [ ] 프로덕션 서버 배포

### SMS
- [ ] NHN Cloud 계정 및 발신번호 등록
- [ ] SMS 발송 테스트 성공
- [ ] 웹훅 수신 테스트 성공

### 네이버 예약
- [ ] 네이버 예약 계정 확인
- [ ] API 또는 크롤링 방식 선택
- [ ] 동기화 테스트 성공

### Google Sheets
- [ ] 서비스 계정 생성 및 권한 부여
- [ ] 스프레드시트 생성
- [ ] 읽기/쓰기 테스트 성공

### Claude API + RAG
- [ ] Claude API 키 발급
- [ ] ChromaDB 정상 작동
- [ ] 문서 인덱싱 테스트
- [ ] 자동 응답 생성 테스트

### 통합 테스트
- [ ] E2E 시나리오 모두 성공
- [ ] 에러 핸들링 확인
- [ ] 부하 테스트 통과

---

## 🚨 트러블슈팅

### SMS 발송 실패
- 발신번호 사전 등록 여부 확인
- API 키 및 서명 정확성 확인
- NHN Cloud 크레딧 잔액 확인

### 네이버 크롤링 실패
- 로그인 페이지 URL 변경 여부 확인
- CAPTCHA 발생 시 → API 방식으로 전환 또는 IP 화이트리스트 등록

### Google Sheets 권한 오류
- 서비스 계정 이메일에 편집 권한 부여 확인
- credentials.json 파일 경로 정확성 확인

### Claude API 타임아웃
- RAG 검색 결과가 너무 많으면 top_k 줄이기
- 네트워크 안정성 확인

---

## 📊 전환 후 모니터링

### 주요 지표
- SMS 발송 성공률 (목표: 95% 이상)
- 자동 응답 신뢰도 (평균 75% 이상)
- API 응답 시간 (평균 500ms 이하)
- 웹훅 수신 지연 (1초 이내)

### 로그 모니터링
```bash
# 실시간 로그 확인
tail -f /var/log/sms-system/app.log | grep "ERROR\|CRITICAL"
```

### 알림 설정
- SMS 발송 실패 시 관리자 알림
- API 에러율 임계값 초과 시 알림
- 서버 다운 시 즉시 알림

---

## 🎉 전환 완료!

축하합니다! 9시간 만에 데모 시스템을 프로덕션 환경으로 성공적으로 전환했습니다.

이제 실제 고객에게 서비스를 제공할 수 있습니다! 🚀
