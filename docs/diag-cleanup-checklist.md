# Diag Infrastructure Cleanup Checklist

리팩토링 후 `diag_logger` 인프라를 완전히 제거하려면 아래 명령들을 실행해
모든 관련 코드를 식별한 후 제거:

## 1. 백엔드 호출 지점 찾기
```bash
grep -rn "diag(" backend/app/ | grep -v "def diag" | grep -v "diag_logger.py"
```

## 2. 백엔드 import 찾기
```bash
grep -rn "from app.diag_logger" backend/
```

## 3. DIAG_BLOCK 마커 찾기
```bash
grep -rn "DIAG_BLOCK_START\|DIAG_BLOCK_END" backend/ frontend/
```

## 4. 프론트엔드 마커 찾기
```bash
grep -rn "X-Diag-\|__diagAction\|X-Request-ID" frontend/src/
```

## 5. 환경변수 / 설정
```bash
grep -rn "DIAG_LEVEL\|DIAG_LOG_DIR\|DIAG_LOGGING" . --include="*.yml" --include=".env*"
```

## 6. 파일 자체
```bash
ls backend/app/diag_logger.py
ls backend/logs/refactor-diag.log*
```

모든 grep 결과가 0건 + diag_logger.py 삭제 + logs/ 디렉토리 정리 = 완전 제거.
