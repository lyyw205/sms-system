"""Pre-send refresh (Option Y) 통합 테스트.

발송 직전 reconcile 훅이 stale 칩 정리와 누락 칩 생성을 실제로 수행하는지
확인한다. Eligibility 필터는 refresh 이후 상태를 기준으로 후보를 뽑아야 함.
"""
import asyncio
from datetime import timedelta

from app.config import today_kst, today_kst_date
from app.db.models import (
    Building,
    MessageTemplate,
    Reservation,
    ReservationSmsAssignment,
    ReservationStatus,
    Room,
    RoomAssignment,
    TemplateSchedule,
)
from app.scheduler.template_scheduler import TemplateScheduleExecutor


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class _MockSMSProvider:
    def __init__(self):
        self.calls = []

    async def send_sms(self, to, message, **kwargs):
        self.calls.append({"to": to, "message": message})
        return {"success": True, "message_id": "mock", "error": None}


def _executor(db):
    return TemplateScheduleExecutor(db, tenant=None)


def _make_building(db):
    b = Building(tenant_id=1, name="본관", is_active=True)
    db.add(b)
    db.flush()
    return b


def _make_room(db, building, room_number="A101", base_capacity=2, is_dormitory=False):
    r = Room(
        tenant_id=1,
        room_number=room_number,
        room_type="더블",
        building_id=building.id,
        is_active=True,
        is_dormitory=is_dormitory,
        base_capacity=base_capacity,
    )
    db.add(r)
    db.flush()
    return r


def _make_reservation(db, *, male=0, female=0, check_in=None, check_out=None):
    check_in = check_in or today_kst()
    check_out = check_out or (today_kst_date() + timedelta(days=1)).strftime("%Y-%m-%d")
    res = Reservation(
        tenant_id=1,
        customer_name="손님",
        phone="01012345678",
        check_in_date=check_in,
        check_in_time="15:00",
        check_out_date=check_out,
        status=ReservationStatus.CONFIRMED,
        male_count=male,
        female_count=female,
    )
    db.add(res)
    db.flush()
    return res


def _assign(db, reservation, room, date=None):
    ra = RoomAssignment(
        tenant_id=1,
        reservation_id=reservation.id,
        room_id=room.id,
        date=date or today_kst(),
        assigned_by="auto",
    )
    db.add(ra)
    db.flush()
    return ra


def _surcharge_template(db, level):
    t = MessageTemplate(
        tenant_id=1,
        template_key=f"add_{level}_person",
        name=f"{level}인 추가요금",
        content=f"{level}인 추가요금 안내",
        is_active=True,
    )
    db.add(t)
    db.flush()
    return t


def _surcharge_schedule(db, template, level):
    s = TemplateSchedule(
        tenant_id=1,
        template_id=template.id,
        schedule_name=f"surcharge_{level}",
        schedule_type="daily",
        hour=13,
        minute=25,
        schedule_category="custom_schedule",
        custom_type=f"surcharge_{level}",
        is_active=True,
    )
    db.add(s)
    db.flush()
    return s


class TestPreSendRefresh:
    def test_refresh_creates_missing_chip(self, db):
        """trigger 경로가 한 번도 안 돌아 칩이 없던 경우에도 발송 직전 refresh 로 생성된다."""
        building = _make_building(db)
        room = _make_room(db, building, base_capacity=2)
        tpl = _surcharge_template(db, 1)
        sched = _surcharge_schedule(db, tpl, 1)

        # excess=1 조건이지만 chip 생성 trigger 가 한 번도 호출되지 않음
        res = _make_reservation(db, male=3)
        _assign(db, res, room)

        # 확인: 현재는 칩이 없음
        assert db.query(ReservationSmsAssignment).count() == 0

        # get_targets 가 refresh 를 트리거해야 함
        targets = _executor(db).get_targets(sched)

        assert [t.id for t in targets] == [res.id]
        chips = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.reservation_id == res.id,
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()
        assert len(chips) == 1, "refresh 로 새 칩이 생성되어야 함"

    def test_refresh_cleans_stale_chip_when_condition_no_longer_holds(self, db):
        """과거엔 excess 였으나 지금은 조건 불만족인 예약: refresh 가 stale 칩 제거."""
        building = _make_building(db)
        room = _make_room(db, building, base_capacity=4)  # 기준 4인
        tpl = _surcharge_template(db, 1)
        sched = _surcharge_schedule(db, tpl, 1)

        # 현재 시점: 4인 예약 (excess=0) — 추가요금 대상 아님
        res = _make_reservation(db, male=4)
        _assign(db, res, room)

        # stale 칩을 직접 주입 (과거에 excess=1 이었다고 가정)
        stale = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res.id,
            template_key=tpl.template_key,
            date=today_kst(),
            assigned_by="auto",
            schedule_id=sched.id,
        )
        db.add(stale)
        db.flush()

        targets = _executor(db).get_targets(sched)

        assert targets == [], "조건 미충족 예약은 refresh 후 대상에서 빠져야 함"
        remaining = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.schedule_id == sched.id,
            ReservationSmsAssignment.sent_at.is_(None),
        ).all()
        assert remaining == [], "stale 칩이 refresh 로 삭제되어야 함"

    def test_refresh_moves_chip_to_correct_level(self, db):
        """excess 레벨이 바뀐 경우: 과거 레벨 칩 제거 + 현재 레벨 칩 생성."""
        building = _make_building(db)
        room = _make_room(db, building, base_capacity=2)
        tpl1 = _surcharge_template(db, 1)
        sched1 = _surcharge_schedule(db, tpl1, 1)
        tpl2 = _surcharge_template(db, 2)
        sched2 = _surcharge_schedule(db, tpl2, 2)

        # 현재 상태: 4명 (excess=2)
        res = _make_reservation(db, male=4)
        _assign(db, res, room)

        # 과거 상태: excess=1 로 sched1 칩이 박혀있었음 (stale)
        stale = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res.id,
            template_key=tpl1.template_key,
            date=today_kst(),
            assigned_by="auto",
            schedule_id=sched1.id,
        )
        db.add(stale)
        db.flush()

        # sched2 를 실행 — refresh 가 sched1 stale 칩 삭제 + sched2 칩 생성
        targets = _executor(db).get_targets(sched2)

        assert [t.id for t in targets] == [res.id]
        # sched1 칩은 사라져야 함
        assert db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.schedule_id == sched1.id,
        ).count() == 0
        # sched2 칩이 새로 생겨야 함
        assert db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.schedule_id == sched2.id,
            ReservationSmsAssignment.sent_at.is_(None),
        ).count() == 1

    def test_refresh_skips_dormitory(self, db):
        """도미토리는 refresh 후에도 대상 아님."""
        building = _make_building(db)
        dorm = _make_room(db, building, base_capacity=2, is_dormitory=True, room_number="D101")
        tpl = _surcharge_template(db, 1)
        sched = _surcharge_schedule(db, tpl, 1)

        res = _make_reservation(db, male=3)
        _assign(db, res, dorm)

        targets = _executor(db).get_targets(sched)
        assert targets == []

    def test_refresh_is_noop_for_standard_schedule(self, db):
        """standard 스케줄은 refresh 훅을 타지 않음 — 기존 동작 유지."""
        tpl = MessageTemplate(
            tenant_id=1, template_key="std_only", name="std",
            content="hi", is_active=True,
        )
        db.add(tpl)
        db.flush()

        sched = TemplateSchedule(
            tenant_id=1,
            template_id=tpl.id,
            schedule_name="std",
            schedule_type="daily",
            hour=9,
            minute=0,
            target_mode="once",
            date_target="today",
            schedule_category="standard",
            is_active=True,
        )
        db.add(sched)
        db.flush()

        # 예약만 있고 칩 없음 — custom 이라면 refresh 가 생성했겠지만 standard 는 그대로
        res = _make_reservation(db)

        targets = _executor(db).get_targets(sched)
        assert res.id in [t.id for t in targets]
        # standard 는 refresh 가 안 돌아서 칩이 생성되지 않는다
        assert db.query(ReservationSmsAssignment).count() == 0

    def test_preview_does_not_trigger_refresh(self, db):
        """preview_targets / for_preview=True 호출 시 refresh 훅을 안 탐 — DB 쓰기 부작용 방지."""
        building = _make_building(db)
        room = _make_room(db, building, base_capacity=2)
        tpl = _surcharge_template(db, 1)
        sched = _surcharge_schedule(db, tpl, 1)

        # refresh 가 돌면 칩이 생성될 조건이지만, 지금은 칩이 없는 상태
        res = _make_reservation(db, male=3)
        _assign(db, res, room)

        # preview 는 칩을 만들지 말아야 함
        targets = _executor(db).get_targets(sched, for_preview=True)
        assert targets == [], "칩이 없으면 preview 대상도 없어야 함"
        assert db.query(ReservationSmsAssignment).count() == 0, \
            "preview 는 DB 쓰기를 유발하면 안 됨"

        # 일반 호출(for_preview=False) 은 여전히 refresh 로 칩 생성
        targets = _executor(db).get_targets(sched)
        assert [t.id for t in targets] == [res.id]
        assert db.query(ReservationSmsAssignment).count() == 1

    def test_preview_targets_method_passes_for_preview(self, db):
        """preview_targets 메서드가 내부적으로 for_preview=True 를 넘겨 refresh 를 막음."""
        building = _make_building(db)
        room = _make_room(db, building, base_capacity=2)
        tpl = _surcharge_template(db, 1)
        sched = _surcharge_schedule(db, tpl, 1)

        res = _make_reservation(db, male=3)
        _assign(db, res, room)

        # preview_targets 경로
        preview = _executor(db).preview_targets(sched)
        assert preview == [], "칩이 없으면 preview 목록 비어야 함"
        assert db.query(ReservationSmsAssignment).count() == 0, \
            "preview_targets 도 DB 쓰기 없어야 함"

    def test_refresh_handles_unregistered_custom_type_gracefully(self, db):
        """등록 안 된 custom_type 은 refresh 가 no-op — 기존 칩 기준으로 진행."""
        tpl = MessageTemplate(
            tenant_id=1, template_key="future_type", name="future",
            content="hi", is_active=True,
        )
        db.add(tpl)
        db.flush()

        sched = TemplateSchedule(
            tenant_id=1,
            template_id=tpl.id,
            schedule_name="future",
            schedule_type="daily",
            hour=13,
            minute=25,
            schedule_category="custom_schedule",
            custom_type="unknown_future_type",  # 레지스트리에 없음
            is_active=True,
        )
        db.add(sched)
        db.flush()

        res = _make_reservation(db)
        # 누군가가 수동으로 꽂은 칩이 있다고 가정
        chip = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res.id,
            template_key=tpl.template_key,
            date=today_kst(),
            assigned_by="manual",
            schedule_id=sched.id,
        )
        db.add(chip)
        db.flush()

        # refresh handler 가 없어도 예외 없이 진행되고, 기존 칩이 기준이 됨
        targets = _executor(db).get_targets(sched)
        assert [t.id for t in targets] == [res.id]


class TestRefreshResilience:
    def test_refresh_swallows_handler_exception(self, db, monkeypatch):
        """refresh handler 가 예외를 던져도 발송 플로우가 중단되지 않음.

        _refresh_custom_chips 의 try/except 가드가 작동하는지 확인. handler 가
        터지면 log 만 남기고 기존 칩 상태 기준으로 eligibility 필터가 돌아야 함.
        """
        building = _make_building(db)
        room = _make_room(db, building, base_capacity=2)
        tpl = _surcharge_template(db, 1)
        sched = _surcharge_schedule(db, tpl, 1)

        res = _make_reservation(db, male=3)
        _assign(db, res, room)

        # 기존 칩이 하나 있다고 가정 (refresh 가 터져도 이 칩 기준으로 발송 대상 판단)
        chip = ReservationSmsAssignment(
            tenant_id=1,
            reservation_id=res.id,
            template_key=tpl.template_key,
            date=today_kst(),
            assigned_by="auto",
            schedule_id=sched.id,
        )
        db.add(chip)
        db.flush()

        # handler 가 예외를 던지도록 monkeypatch
        def _raising_handler(db_arg, target_date_arg):
            raise RuntimeError("boom")

        import app.services.custom_schedule_registry as registry
        monkeypatch.setitem(
            registry.PRE_SEND_REFRESH_HANDLERS, "surcharge_1", _raising_handler,
        )

        # get_targets 가 예외 없이 완주해야 함
        targets = _executor(db).get_targets(sched)
        assert [t.id for t in targets] == [res.id], \
            "refresh 예외는 삼키고 기존 칩 기준으로 후보 뽑아야 함"

    def test_refresh_is_idempotent_on_repeated_calls(self, db):
        """같은 스케줄 refresh 를 연속 호출해도 칩 상태가 바뀌지 않음.

        surcharge_1/2/3/4 가 13:25 동시 트리거될 때 reconcile 이 여러 번 돌아도
        정합성 문제가 없음을 문서화한다.
        """
        building = _make_building(db)
        room = _make_room(db, building, base_capacity=2)
        tpl = _surcharge_template(db, 1)
        sched = _surcharge_schedule(db, tpl, 1)

        res = _make_reservation(db, male=3)
        _assign(db, res, room)

        executor = _executor(db)

        # 1차 호출
        targets_1 = executor.get_targets(sched)
        chips_after_1 = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()

        # 2차 호출 — 동일 조건
        targets_2 = executor.get_targets(sched)
        chips_after_2 = db.query(ReservationSmsAssignment).filter(
            ReservationSmsAssignment.schedule_id == sched.id,
        ).all()

        assert [t.id for t in targets_1] == [t.id for t in targets_2] == [res.id]
        assert len(chips_after_1) == len(chips_after_2) == 1
        assert chips_after_1[0].id == chips_after_2[0].id, \
            "refresh 재호출로 칩이 재생성되면 안 됨 (기존 칩 유지)"


class TestCustomSendConditionGuard:
    """send_condition_* 가 custom 스케줄에 실수로 설정돼도 gender 비율로 skip 되지 않아야 함."""

    def test_send_condition_is_ignored_for_custom_schedule(self, db):
        """custom 스케줄 + send_condition 불만족 상황에서도 get_targets 까지 도달."""
        building = _make_building(db)
        room = _make_room(db, building, base_capacity=2)
        tpl = _surcharge_template(db, 1)

        # 말도 안 되는 비율(100 이상)로 설정 — standard 라면 무조건 skip
        sched = TemplateSchedule(
            tenant_id=1,
            template_id=tpl.id,
            schedule_name="surcharge with stale send_condition",
            schedule_type="daily",
            hour=13,
            minute=25,
            schedule_category="custom_schedule",
            custom_type="surcharge_1",
            is_active=True,
            send_condition_date="today",
            send_condition_ratio=100.0,
            send_condition_operator="gte",
        )
        db.add(sched)
        db.flush()

        res = _make_reservation(db, male=3, female=0)
        _assign(db, res, room)

        executor = _executor(db)
        executor.sms_provider = _MockSMSProvider()

        result = _run_async(executor.execute_schedule(sched.id))

        # send_condition 가드가 작동했다면 발송이 1건 성공해야 함
        assert result.get("success") is True
        assert result.get("sent_count") == 1, (
            f"custom 에 설정된 send_condition 때문에 skip 됨: {result}"
        )

    def test_send_condition_still_applies_to_standard_schedule(self, db):
        """standard 스케줄은 기존대로 send_condition 적용 — 회귀 방지."""
        tpl = MessageTemplate(
            tenant_id=1, template_key="std_cond", name="std", content="hi", is_active=True,
        )
        db.add(tpl)
        db.flush()

        sched = TemplateSchedule(
            tenant_id=1,
            template_id=tpl.id,
            schedule_name="std with send_condition",
            schedule_type="daily",
            hour=9,
            minute=0,
            target_mode="once",
            date_target="today",
            schedule_category="standard",
            is_active=True,
            send_condition_date="today",
            send_condition_ratio=100.0,
            send_condition_operator="gte",
        )
        db.add(sched)
        db.flush()

        # male=1, female=1 → ratio=1.0 < 100 → gte 불만족 → skip 되어야 함
        res = Reservation(
            tenant_id=1, customer_name="손님", phone="01012345678",
            check_in_date=today_kst(), check_in_time="15:00",
            status=ReservationStatus.CONFIRMED,
            male_count=1, female_count=1,
        )
        db.add(res)
        db.flush()

        executor = _executor(db)
        executor.sms_provider = _MockSMSProvider()

        result = _run_async(executor.execute_schedule(sched.id))

        # send_condition 미충족으로 skip 되어야 함
        assert result.get("success") is True
        assert result.get("sent_count", 0) == 0
        assert "Send condition" in (result.get("message") or ""), result
