# SMS 게이트웨이 — 핸드오프

> 작성 2026-08-21 · 상태: **백엔드 완료(미배포) / 앱·UI 미착수**
> 목적: 안드로이드 앱(APK)을 별도 레포에서 이어서 만들기 위한 인계 문서
> 원본 코드는 같은 PC에 있으니 필요하면 직접 열어보세요 — 이 문서는 **지도**입니다.

로컬 경로: `/home/lyyw2/repos/sms-system`

---

## 0. 한 줄 요약

> 고객이 보낸 문자를 **안드로이드 폰이 받아서 우리 서버에 적재**하고,
> 관리 화면에서 **개별 답장**을 보내는 채널. 기존 알리고(대량·장문·MMS 발송)와 **완전히 분리**된 별개 경로.

---

## 1. 왜 만드나 / 무엇을 안 하나

| 용도 | 게이트웨이 | 알리고 (기존, 무수정) |
|------|-----------|---------------------|
| 고객 문자 **수신** | ✅ 이것 때문에 만듦 | ❌ 불가 |
| 개별 **답장** (짧은 1:1) | ✅ | — |
| 폰에서 직원이 직접 보낸 발신 **캡처** | ✅ | — |
| MMS **수신** (입금 캡처 등) | ✅ | — |
| 템플릿 자동발송 / 장문(LMS) / 파티 MMS **발송** | ❌ **안 함** | ✅ 그대로 유지 |

**중요**: `app/factory.py` 의 SMS provider 는 **건드리지 않았습니다.** 거기 끼우면 템플릿 자동발송이 전부 폰으로 넘어가 버림. 게이트웨이는 독립 채널이라 한쪽이 죽어도 다른 쪽에 영향 없음.

---

## 2. 작업한 파일 (전부)

| 파일 | 상태 | 내용 |
|------|------|------|
| `backend/app/db/models.py` | 수정 | L612~714 모델 3개 추가 / L4 `LargeBinary` import / L717~ `_register` 목록에 3개 추가 |
| `backend/app/api/gateway.py` | **신규 853줄** | 엔드포인트 14개 전부 |
| `backend/app/main.py` | 수정 | L23 import, L226 `include_router` |

그 외 파일은 **한 줄도 안 건드렸습니다.**

---

## 3. DB 스키마 (Supabase PostgreSQL — 기존 DB와 동일)

`init_db()` 의 `Base.metadata.create_all` 이 배포 시 자동 생성. 별도 마이그레이션 불필요.

### `sms_devices` — 등록된 폰
`device_uid`(앱 생성 UUID) · `token`(인증용, unique) · `pairing_code`(운영자에게 불러줄 코드)
`is_active`(승인 여부) · `phone_number` · `model` · `app_version` · `last_seen_at` · `battery_level`

### `sms_messages` — 문자 원장 (수신·발신 통합)
- `direction`: `in` | `out`
- `peer_phone`: 상대 번호, **숫자만** 정규화 (`01055973129`) — `reservations.phone` 형식과 동일
- `status`: in → `received` / out → `pending`→`sending`→`sent`|`failed`
- `source`: `gateway`(앱 처리) | `phone`(폰 문자앱 발신 캡처) | `system`(큐잉만 됨)
- `client_msg_id`: 앱 생성 UUID — **재시도 중복 방지** (unique with tenant)
- `provider_id`: 폰 `content://sms` 의 `_id` — **폰 발신 이중감지 방지** (unique with tenant+direction)
- `reservation_id`: 번호로 자동 매칭한 예약 (best-effort, 실패해도 적재는 진행)
- `is_mms` · `occurred_at`(폰 기준 실제 시각) · `claimed_at` · `attempts` · `error`

### `sms_attachments` — MMS 첨부
`message_id` FK · `content_type` · `filename` · `size_bytes` · `data`(**LargeBinary, DB 직접 저장**)

> 파일이 아닌 DB 저장 이유: 운영 백엔드 컨테이너에 첨부용 볼륨이 없어 파일로 두면 **재배포 시 유실**됨.
> 건당 2MB 상한. 사진이 잦아지면 EC2 볼륨으로 옮기는 것 검토 (§7 참조).

---

## 4. API 명세 — **앱 개발 시 이것만 보면 됨**

Base: `{SERVER}/api/gateway` · 기기 인증 헤더: `X-Device-Token: <token>`

### 기기용 (앱이 호출)

| Method | Path | Body / 설명 |
|--------|------|-------------|
| POST | `/enroll` | `{tenant_slug, device_uid, model?, app_version?, phone_number?}` → `{token, pairing_code, is_active}` · **인증 불필요** · 같은 `device_uid` 면 멱등(같은 토큰 반환) |
| GET | `/status` | → `{is_active, pairing_code, tenant_name, poll_interval_sec, daily_send_limit, min_send_gap_sec}` · **동작 설정값을 서버가 내려줌 → 앱에 설정화면 불필요** |
| POST | `/heartbeat` | `{battery_level?, app_version?, phone_number?}` |
| POST | `/inbound` | `{messages:[{client_msg_id, peer_phone, body?, occurred_at?, is_mms?, provider_id?}]}` → `[{client_msg_id, message_id, duplicate}]` |
| POST | `/attachment` | multipart: `message_id` + `file` → `{attachment_id, size_bytes}` · 2MB 초과 시 413 |
| POST | `/sent` | `{messages:[{provider_id, peer_phone, body?, occurred_at?, is_mms?}]}` → `{created}` · 폰 문자앱 발신 캡처용 |
| GET | `/outbox` | → `[{id, to, text}]` · 최대 10건 claim · 재조회 시 같은 건 안 나옴 |
| POST | `/result` | `{results:[{id, success, error?, provider_id?, occurred_at?}]}` |

### 운영자용 (JWT + `X-Tenant-Id`, ADMIN 이상)

`GET /devices` · `POST /devices/approve {pairing_code, label?}` · `DELETE /devices/{id}`
`GET /messages?peer_phone=&limit=` · `GET /attachments/{id}` · `POST /reply {peer_phone, text}`

### 상태코드 규약
`401` 토큰 없음/무효 · `403` **승인 대기 중인 기기** · `404` 잘못된 tenant_slug · `413` 첨부 초과 · `429` 미승인 기기 5대 초과 · `409` 승인된 기기 0대인데 reply 시도

---

## 5. 페어링 흐름 (사용자가 파라미터를 입력하지 않게 하는 게 요구사항)

```
APK 설치 → 권한 허용 → 앱이 스스로 POST /enroll
   → 화면에 pairing_code 표시 (예: K7X2-9QMR-4T8W)
   → 운영자에게 코드만 알려줌 → 관리 화면에서 승인
   → is_active=true → 그때부터 동작
```

- `tenant_slug` 와 서버 주소는 **APK 빌드 시점에 박아둠** (사용자 입력 0개)
- 승인 전에는 `/inbound` `/outbox` 등 전부 403
- 기기 폐기 시 토큰 즉시 재발급되어 기존 토큰 무효화

---

## 6. 앱 구현 시 반드시 지킬 것

1. **수신은 `BroadcastReceiver`** (`SMS_RECEIVED_ACTION`). 폴링 아님. 기본 SMS 앱이 아니어도 됨.
2. **발신은 폴링** — `GET /outbox` 를 `poll_interval_sec`(기본 10초) 주기로. 서버→폰 방향 호출은 불가(NAT). FCM 미사용(구글 경유 회피).
3. **폰 발신 캡처**: `content://sms` 에 `ContentObserver` + `READ_SMS`. `_id > 마지막처리` 만 조회. 전송중(type=4)→완료(type=2) 로 **두 번 감지되므로** `provider_id` 로 서버가 걸러냄.
4. **RCS(채팅+)는 잡히지 않음** — `content://sms` 에 저장되지 않고 제3자 앱 접근 경로가 없음. **게이트웨이 폰의 RCS를 꺼야 함.** 끄면 상대가 갤럭시여도 SMS로 폴백되어 전부 잡힘.
5. **우리 앱 발송분은 폰 발신함에 안 남음** (기본 SMS 앱만 쓰기 가능) → 중복 걱정 없음. 대신 직원이 폰 문자앱에서 전체 대화 맥락을 못 봄 → 관리 화면에서 봐야 함.
6. **발송 안전장치**: `daily_send_limit`(기본 200), `min_send_gap_sec`(기본 3) 를 앱이 지킬 것. 통신사 스팸 차단 예방.
7. 필요 권한: `RECEIVE_SMS` `SEND_SMS` `READ_SMS` `RECEIVE_MMS` `POST_NOTIFICATIONS` + 배터리 최적화 제외 + 부팅 시 자동 시작 + Foreground Service.

---

## 7. 미결정 — 진행 전 확인 필요

| # | 항목 | 상태 |
|---|------|------|
| 1 | **HTTPS** | 운영 nginx 인증서가 플레이스홀더(`your-domain.com`)라 **현재 평문 HTTP**. 선택지: (A) 도메인+Let's Encrypt ← 권장, 관리화면도 같이 해결 (B) 자체 CA + 앱 피닝 (C) 평문 ← 비권장. 사용자: "나중에 붙일 것" |
| 2 | **첨부 저장 위치** | 현재 DB(bytea). Supabase 플랜이 무료(500MB 한도)면 EC2 볼륨으로 이전 검토. 현재 DB 총 47MB |
| 3 | 앱 패키지명 / 서버 주소 | 미정. APK 빌드 시 상수로 박을 값 |

**빌드 방식**: 로컬 WSL 에 JDK/Android SDK 없음. `gh` CLI 는 인증됨 → **GitHub Actions 로 APK 빌드 후 아티팩트 다운로드** 방식 권장.

---

## 8. 검증 방법 (재현 가능)

운영 무접촉으로 전 흐름 검증 완료 — **39개 항목 ALL PASS**.

```
운영 이미지로 일회용 컨테이너 기동
  → 변경 파일 3개 복사
  → DATABASE_URL=sqlite:////tmp/gwtest.db 로 오버라이드
  → FastAPI TestClient 로 전 흐름 실행
  → 컨테이너 삭제
```

커버 범위: 페어링 멱등·승인 전 403·수신 중복방지·번호 정규화(+82→0)·MMS 2MB 상한 및 바이트 무결성·claim 후 재조회 0건·폰 발신 이중감지 차단·토큰 폐기 즉시 무효.

> 테스트 스크립트는 세션 스크래치패드에 있었고 레포에 커밋하지 않았습니다. 필요하면 위 절차로 재작성.

---

## 9. 다음 작업

1. **안드로이드 앱** (별도 레포) — §4 API, §6 제약 준수
2. **배포** — 커밋 → 서버 반영. 새 테이블 3개만 추가되고 기존 경로 무영향
3. **관리 화면** (React) — 대화 목록 / 답장 / 첨부 뷰 / 기기 승인. `frontend/src` 에 게이트웨이 관련 코드 **현재 0줄**

권장 순서: **앱 → 배포 → 화면** (실데이터가 들어와야 화면을 제대로 만들 수 있음)

---

## 10. 참고 (원본 레포 규약)

- 프로젝트 전반: `CLAUDE.md` · 프론트 디자인: `frontend/CLAUDE.md`
- 멀티테넌트: `X-Tenant-Id` 헤더 + `get_tenant_scoped_db()`. `TenantMixin` 모델은 SELECT/INSERT 자동 필터링 → **신규 모델은 `models.py` 하단 `_register` 목록에 반드시 추가** (3개 모두 등록 완료)
- 계측: `app.diag_logger.diag()` — 게이트웨이 주요 분기에 `level="critical"` 로 심어둠 (`gateway.device.enrolled` / `gateway.inbound.received` / `gateway.attachment.stored` / `gateway.phone_sent.captured` / `gateway.send.result` / `gateway.reply.queued` / `gateway.device.approved` / `gateway.device.revoked`)
- 운영 접속 정보·DB 접속 문자열은 **이 문서에 포함하지 않음** (레포 PUBLIC). 서버의 `backend/.env` 및 사용자 메모 참조.
