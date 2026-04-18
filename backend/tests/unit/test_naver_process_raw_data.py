"""RealReservationProvider._process_raw_data 회귀 테스트.

핵심 검증: 취소 건이 같은 biz_item + name + phone 의 확정 건과 공존해도
드롭되지 않고 status='cancelled' 로 그대로 반환되어야 한다.
(GAS 레거시 rebook 필터 제거의 회귀 방지)
"""
import asyncio

from app.real.reservation import RealReservationProvider


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mk_item(*, booking_id, status, biz_item_id=111, name="조하민", phone="01055453761",
             start_date="2026-04-17", end_date="2026-04-18", user_id="u1"):
    """Create a mock Naver API item."""
    return {
        "bookingId": booking_id,
        "bookingStatusCode": status,  # 'RC03' | 'RC04'
        "bizItemId": biz_item_id,
        "name": name,
        "phone": phone,
        "userId": user_id,
        "startDate": start_date,
        "endDate": end_date,
        "startTime": "15:00",
        "bookingCount": 1,
        "confirmedDateTime": "2026-04-01T00:00:00Z",
        "cancelledDateTime": "2026-04-15T00:00:00Z" if status == "RC04" else "",
    }


def _make_provider(monkeypatch):
    provider = RealReservationProvider(business_id="test", cookie="test-cookie")

    async def _no_user_fetch(_uid):
        return None  # skip enrichment (covered separately)

    monkeypatch.setattr(provider, "get_user_info", _no_user_fetch)
    return provider


class TestRebookFilterRemoval:
    def test_cancelled_is_kept_even_when_confirmed_shares_biz_name_phone(self, monkeypatch):
        """같은 biz_item+name+phone 으로 확정건이 존재해도 취소건이 결과에 남는다."""
        provider = _make_provider(monkeypatch)

        data = [
            _mk_item(booking_id=1001, status="RC04"),  # 과거 취소
            _mk_item(booking_id=1002, status="RC03"),  # 재예약 (같은 사람/방)
        ]

        out = _run(provider._process_raw_data(data))

        # 두 건 모두 결과에 포함돼야 함 (예전엔 취소건이 드롭됐었음)
        assert len(out) == 2, f"취소건이 드롭되면 안 됨 — 결과: {out}"
        statuses = {r["external_id"]: r["status"] for r in out}
        assert statuses["1001"] == "cancelled"
        assert statuses["1002"] == "confirmed"

    def test_multiple_rebook_cycles_all_cancelled_kept(self, monkeypatch):
        """연쇄 재예약(C1 취소 → C2 취소 → C3 확정)의 취소 건 모두 보존."""
        provider = _make_provider(monkeypatch)

        data = [
            _mk_item(booking_id=2001, status="RC04"),
            _mk_item(booking_id=2002, status="RC04"),
            _mk_item(booking_id=2003, status="RC03"),
        ]

        out = _run(provider._process_raw_data(data))

        assert len(out) == 3
        cancelled_ids = {r["external_id"] for r in out if r["status"] == "cancelled"}
        confirmed_ids = {r["external_id"] for r in out if r["status"] == "confirmed"}
        assert cancelled_ids == {"2001", "2002"}
        assert confirmed_ids == {"2003"}

    def test_plain_cancellation_still_works(self, monkeypatch):
        """재예약이 없는 단순 취소 — 회귀 방지 (기본 동작 불변)."""
        provider = _make_provider(monkeypatch)

        data = [
            _mk_item(booking_id=3001, status="RC04"),
        ]

        out = _run(provider._process_raw_data(data))

        assert len(out) == 1
        assert out[0]["external_id"] == "3001"
        assert out[0]["status"] == "cancelled"

    def test_cancelled_gets_cancelled_at_metadata(self, monkeypatch):
        """취소 건에 cancelled_at 타임스탬프가 채워져 sync 가 반영할 수 있어야 함."""
        provider = _make_provider(monkeypatch)

        data = [_mk_item(booking_id=4001, status="RC04")]

        out = _run(provider._process_raw_data(data))

        assert out[0]["cancelled_at"] == "2026-04-15T00:00:00Z"

    def test_different_biz_item_also_kept(self, monkeypatch):
        """서로 다른 biz_item 으로 확정+취소가 공존할 때도 둘 다 유지 (회귀 방지)."""
        provider = _make_provider(monkeypatch)

        data = [
            _mk_item(booking_id=5001, status="RC04", biz_item_id=111),
            _mk_item(booking_id=5002, status="RC03", biz_item_id=222),  # 다른 방
        ]

        out = _run(provider._process_raw_data(data))

        assert len(out) == 2
