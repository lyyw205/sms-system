"""LB-05 수정 검증: POST /api/reservations 의 check_out_date '' → None 정규화.

배경: 수동 생성(create_reservation)이 check_out_date 를 body 에서 raw 로 Reservation() 에 넣어,
  네이버 생성 sibling(naver_sync.py:715 `or None`)과 달리 '' 를 그대로 저장했다.
  '' 는 is_(None)/func.max SQL 사이트를 오분류시킨다(핀은 없음 — create 기본 False).

수정: 생성자에서 `check_out_date=reservation.check_out_date or None` (naver sibling 미러).
  이 테스트는 *수정 후* 동작(엔드포인트 직접 호출)을 핀한다.
"""
import asyncio
from types import SimpleNamespace

from app.api.reservations import create_reservation
from app.api.reservations_shared import ReservationCreate
from app.db.models import Reservation


def _run(coro):
    # asyncio.run() 은 공유 이벤트루프를 닫아 후속 async 테스트를 깨뜨림 — 코드베이스 패턴 준수.
    return asyncio.get_event_loop().run_until_complete(coro)


def _create(db, **kwargs):
    defaults = dict(
        customer_name="tester",
        phone="01000000000",
        check_in_date="2026-06-20",
        check_in_time="15:00",
    )
    defaults.update(kwargs)
    payload = ReservationCreate(**defaults)
    user = SimpleNamespace(username="tester")
    _run(create_reservation(reservation=payload, db=db, current_user=user))
    return db.query(Reservation).filter(Reservation.customer_name == defaults["customer_name"]).first()


class TestCreateCheckoutEmptyStringNormalize:
    def test_empty_checkout_stored_as_none(self, db):
        row = _create(db, check_out_date="")
        assert row is not None
        assert row.check_out_date is None  # '' 가 아니라 None

    def test_real_checkout_preserved(self, db):
        row = _create(db, customer_name="multi", check_out_date="2026-06-23")
        assert row.check_out_date == "2026-06-23"

    def test_none_checkout_stays_none(self, db):
        row = _create(db, customer_name="single", check_out_date=None)
        assert row.check_out_date is None
