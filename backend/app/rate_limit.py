"""
Rate Limiting configuration — slowapi Limiter instance
Separated to avoid circular imports between main.py and api/auth.py
"""
from fastapi import Request
from slowapi import Limiter


def _get_real_ip(request: Request) -> str:
    """X-Forwarded-For 파싱 — nginx가 추가한 마지막 IP 사용 (스푸핑 방지)"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ips = [ip.strip() for ip in forwarded.split(",")]
        return ips[-1] if ips else (request.client.host if request.client else "unknown")
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_real_ip)
