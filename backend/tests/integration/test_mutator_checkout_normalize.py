"""LB-04 수정 검증: mutator 의 check_out_date 빈문자열('') → None 정규화.

배경: PUT /api/reservations/{id} 가 body {"check_out_date": ""} 를 받으면
  - validator(_validate_dates)는 '' 가 falsy 라 단락 → 통과
  - pydantic Optional[str] 은 '' 를 None 으로 coerce 안 함
  → '' 가 mutator 까지 도달. 수정 전에는 '' 가 그대로 저장되어
    (1) is_(None)/func.max SQL 사이트 오분류, (2) check_out_pinned=True 영구 핀 → 네이버 정정 차단.

수정: apply_changes 루프에서 check_out_date == '' → None 정규화 (단일소스).
  check_in_date(nullable=False)는 정규화 제외.

이 테스트는 *수정 후의* 동작을 핀한다 (no-op 아님 — Phase C 버그 수정).
"""
from app.db.models import Reservation, ReservationStatus
from app.services.reservation_mutator import ReservationMutator, ChangeSource


def _make_reservation(db, **kwargs):
    defaults = dict(
        tenant_id=1,
        customer_name="naver홍길동",
        phone="01000000000",
        check_in_date="2026-05-20",
        check_in_time="15:00",
        check_out_date="2026-05-22",
        status=ReservationStatus.CONFIRMED,
    )
    defaults.update(kwargs)
    r = Reservation(**defaults)
    db.add(r)
    db.flush()
    return r


class TestCheckoutEmptyStringNormalize:
    def test_empty_checkout_stored_as_none_not_empty(self, db):
        """기존 checkout 이 있는 예약에 '' PUT → '' 가 아닌 None 으로 저장."""
        r = _make_reservation(db, check_out_date="2026-05-22")
        ReservationMutator.apply_changes(
            db, r, ChangeSource.MANUAL,
            {"check_out_date": ""},
        )
        assert r.check_out_date is None  # '' 가 아니라 None

    def test_clearing_real_checkout_sets_pin(self, db):
        """실제 checkout 을 비우는 건 수동 편집 → 핀 설정(의도된 pin 정책 유지)."""
        r = _make_reservation(db, check_out_date="2026-05-22")
        applied = ReservationMutator.apply_changes(
            db, r, ChangeSource.MANUAL,
            {"check_out_date": ""},
        )
        assert "check_out_date" in applied           # old(date) != None → applied
        assert r.check_out_pinned is True
        # 방명록에도 기록 (check_out_date 는 NAVER guarded)
        assert "check_out_date" in r.manually_edited_fields

    def test_empty_checkout_on_single_day_is_noop_no_spurious_pin(self, db):
        """이미 당일(check_out=None) 예약에 '' PUT → 변화 없음, 헛된 핀 안 생김.

        수정 전 버그: None != '' → applied → 헛된 핀. 수정 후: '' →None, None==None → no-op.
        """
        r = _make_reservation(db, check_out_date=None)
        assert r.check_out_pinned in (False, None)
        applied = ReservationMutator.apply_changes(
            db, r, ChangeSource.MANUAL,
            {"check_out_date": ""},
        )
        assert r.check_out_date is None
        assert "check_out_date" not in applied        # None == None → 미적용
        assert not r.check_out_pinned                  # 헛된 핀 없음

    def test_real_checkout_change_unaffected(self, db):
        """정상 날짜 변경은 영향 없음 (정규화는 '' 에만)."""
        r = _make_reservation(db, check_out_date="2026-05-22")
        ReservationMutator.apply_changes(
            db, r, ChangeSource.MANUAL,
            {"check_out_date": "2026-05-25"},
        )
        assert r.check_out_date == "2026-05-25"
        assert r.check_out_pinned is True

    def test_check_in_date_empty_not_normalized(self, db):
        """check_in_date(nullable=False)는 정규화 대상 아님 — '' 가 None 으로 바뀌지 않는다.

        (제약 위반/크래시 방지. check_in '' 자체는 별도 검증 대상.)
        """
        r = _make_reservation(db, check_in_date="2026-05-20")
        ReservationMutator.apply_changes(
            db, r, ChangeSource.MANUAL,
            {"check_in_date": ""},
        )
        assert r.check_in_date == ""   # None 아님 — 정규화 미적용
