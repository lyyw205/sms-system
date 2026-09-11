"""예약 필드 수정 감사 로그 검증.

배경: 2026-09-10 에 예약 44건의 전화번호가 끝자리 자리바꿈으로 무단 변조됐는데,
객실/템플릿/건물과 달리 **예약 수정만 감사 기록이 없어** 행위자를 activity_logs
로는 특정하지 못했다 (nginx 접근 로그는 이후 재배포로 소실). 값 변경 자체는
`manually_edited_fields` 타임스탬프로 역추적했지만, "누가" 는 정황으로만 남았다.

그래서 PUT /api/reservations/{id} 도 before/after + 행위자를 남긴다.
"""
import asyncio
import json
from types import SimpleNamespace

from app.api.reservations import update_reservation
from app.api.reservations_shared import ReservationUpdate
from app.db.models import ActivityLog, Reservation, ReservationStatus

_USER = SimpleNamespace(username="tjdgh")


def _run(coro):
    """asyncio.run 은 루프를 닫아 get_event_loop() 기반 기존 테스트를 깨뜨린다 — 저장소 관례."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _res(db, **over):
    base = dict(
        tenant_id=1, customer_name="서진경", phone="01050444240",
        check_in_date="2026-09-11", check_in_time="15:00", check_out_date="2026-09-12",
        status=ReservationStatus.CONFIRMED, booking_source="naver",
        naver_booking_id="1331536330", section="room",
    )
    base.update(over)
    res = Reservation(**base)
    db.add(res)
    db.commit()
    return res


def _audit(db):
    return db.query(ActivityLog).filter(
        ActivityLog.activity_type == "reservation_updated").all()


class TestReservationAudit:
    def test_phone_change_records_before_after_and_actor(self, db):
        """사건 재현 — 끝자리 자리바꿈이 행위자와 함께 남아야 한다."""
        res = _res(db)
        _run(update_reservation(res.id, ReservationUpdate(phone="01050444420"), db, _USER))

        row = _audit(db)[0]
        detail = json.loads(row.detail)
        assert detail["changes"]["phone"] == {
            "before": "01050444240", "after": "01050444420"
        }
        assert detail["reservation_id"] == res.id
        assert row.created_by == "tjdgh"
        assert "phone" in row.title

    def test_no_log_when_nothing_actually_changed(self, db):
        """폼 전체 재제출 등 값이 같은 멱등 호출은 감사를 남기지 않는다 (노이즈 차단)."""
        res = _res(db)
        _run(update_reservation(res.id, ReservationUpdate(phone="01050444240"), db, _USER))
        assert _audit(db) == []

    def test_rejected_field_is_not_recorded_as_changed(self, db):
        """mutator 가 거부한 필드는 감사에 안 남아야 한다 — 감사가 거짓말하면 안 된다.

        payload diff 가 아니라 apply_changes 반환값을 쓰는 이유.
        """
        res = _res(db, section="activity")
        _run(update_reservation(
            res.id, ReservationUpdate(section="room", phone="01011112222"), db, _USER))

        rows = _audit(db)
        changes = json.loads(rows[0].detail)["changes"]
        assert "phone" in changes            # 통과한 필드는 기록
        assert "section" not in changes      # section_locked 로 거부 → 기록 없음
        assert res.section == "activity"

    def test_multiple_fields_in_one_request(self, db):
        res = _res(db)
        _run(update_reservation(
            res.id,
            ReservationUpdate(phone="01033334444", customer_name="서진경2"),
            db, _USER,
        ))
        changes = json.loads(_audit(db)[0].detail)["changes"]
        assert changes["phone"]["after"] == "01033334444"
        assert changes["customer_name"] == {"before": "서진경", "after": "서진경2"}

    def test_status_enum_is_json_serializable(self, db):
        """status 는 Enum — detail 직렬화가 깨지면 감사 자체가 유실된다."""
        res = _res(db, status=ReservationStatus.CANCELLED)
        _run(update_reservation(res.id, ReservationUpdate(status="confirmed"), db, _USER))

        changes = json.loads(_audit(db)[0].detail)["changes"]
        assert changes["status"] == {"before": "cancelled", "after": "confirmed"}
