"""
Refactor 2026-04 진단 로그 전용 모듈.

7일 집중 감시용. 감시 완료 후 cleanup:
  1. 환경변수 DIAG_LOGGING=false 로 비활성화
  2. (옵션) 소스 전수 grep으로 diag() 호출 제거
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler

_DIAG_ENABLED = os.environ.get("DIAG_LOGGING", "true").lower() == "true"
_logger = None


def get_diag_logger():
    global _logger
    if _logger:
        return _logger

    _logger = logging.getLogger("refactor_diag")

    if not _DIAG_ENABLED:
        _logger.addHandler(logging.NullHandler())
        _logger.setLevel(logging.CRITICAL + 1)
        _logger.propagate = False
        return _logger

    log_dir = os.environ.get("DIAG_LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    handler = TimedRotatingFileHandler(
        f"{log_dir}/refactor-diag.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    return _logger


def diag(event: str, **kwargs):
    """모든 진단 로그는 이 함수만 사용. Cleanup 시 grep 대상."""
    if not _DIAG_ENABLED:
        return
    logger = get_diag_logger()
    from app.db.tenant_context import current_tenant_id
    kwargs.setdefault("tid", current_tenant_id.get())
    kv = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"[{event}] {kv}")
