# Party MMS Images

이 디렉토리는 `party3_today_mms` 템플릿이 발송할 MMS 에 첨부될 이미지를 담습니다.

## 필요 파일

```
party01.jpg
party02.jpg
party03.jpg
```

세 파일이 모두 존재해야 MMS 가 발송됩니다. 한 개라도 없으면 `send_party_mms()` 는 즉시
실패 반환 (`error="MMS 이미지 누락: ..."`).

## 배치 방법

레거시 Lightsail 서버(`15.164.246.59`) 의 `/home/ubuntu/static/party0{1,2,3}.jpg` 를
복사해서 이 디렉토리에 배치:

```bash
# 로컬에서 레거시 서버로부터 이미지 다운로드
scp ubuntu@15.164.246.59:/home/ubuntu/static/party01.jpg ./
scp ubuntu@15.164.246.59:/home/ubuntu/static/party02.jpg ./
scp ubuntu@15.164.246.59:/home/ubuntu/static/party03.jpg ./

# 레포에 커밋 (이미지는 ~90KB 정도로 작음)
git add party01.jpg party02.jpg party03.jpg
git commit -m "chore(mms): add party MMS images from legacy proxy server"
```

## 참조

- `backend/app/real/sms.py:PARTY_MMS_IMAGE_DIR` — 이 디렉토리 경로
- `backend/app/real/sms.py:send_party_mms` — 이미지 읽어 Aligo /send_mass/ 에 첨부
