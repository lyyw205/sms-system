"""
One-off migration: 도미토리 bed_order 갭 백필.

9e9590a 커밋에서 도입한 _compact_bed_orders_in_cells() 헬퍼를 오늘 이후
도미토리 배정에 적용해 기존 갭을 정리한다.

실행:
  --dry-run  : 변경 예정 내역만 출력 (DB 수정 없음)
  --apply    : 실제 수정

시점: 2026-04-21 (9e9590a 커밋 직후 일회성 백필)
"""
import argparse
from datetime import date
from collections import defaultdict

from app.db.database import SessionLocal
from app.db.models import RoomAssignment, Room, Reservation
from app.db.tenant_context import bypass_tenant_filter
from app.services.room_assignment import _compact_bed_orders_in_cells


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    if not (args.dry_run or args.apply):
        p.error("--dry-run 또는 --apply 중 하나 필요")

    today = date.today().isoformat()
    tok = bypass_tenant_filter.set(True)
    try:
        db = SessionLocal()
        dorm_rooms = {
            r.id: (r.room_number, r.tenant_id)
            for r in db.query(Room).filter(Room.is_dormitory == True).all()
        }
        rows = (
            db.query(
                RoomAssignment.room_id,
                RoomAssignment.date,
                RoomAssignment.bed_order,
                RoomAssignment.reservation_id,
                RoomAssignment.tenant_id,
            )
            .filter(
                RoomAssignment.room_id.in_(dorm_rooms.keys()),
                RoomAssignment.date >= today,
            )
            .all()
        )

        cells = defaultdict(list)
        for r in rows:
            cells[(r[0], r[1])].append((r[2], r[3]))

        gap_cells = []
        for key, orders in cells.items():
            bed_orders = sorted([o for o, _ in orders if o and o > 0])
            if not bed_orders:
                continue
            expected = list(range(1, len(bed_orders) + 1))
            if bed_orders != expected:
                gap_cells.append(key)

        print(f"오늘({today}) 이후 도미토리 갭 셀: {len(gap_cells)}개")

        if not gap_cells:
            print("정리할 갭이 없습니다.")
            return

        for rid, d in gap_cells:
            rn, tid = dorm_rooms.get(rid, ("?", "?"))
            assignments = (
                db.query(RoomAssignment)
                .filter(
                    RoomAssignment.room_id == rid,
                    RoomAssignment.date == d,
                )
                .order_by(RoomAssignment.bed_order, RoomAssignment.id)
                .all()
            )
            print(f"\n--- tid={tid} room={rn} date={d}")
            for a in assignments:
                res = db.query(Reservation).filter(Reservation.id == a.reservation_id).first()
                name = res.customer_name if res else "(?)"
                print(f"  res_id={a.reservation_id} name={name} bed_order={a.bed_order}")

        if args.dry_run:
            print("\n[DRY-RUN] 실제 변경 없음. --apply 로 다시 실행하세요.")
            return

        cell_set = set(gap_cells)
        changed = _compact_bed_orders_in_cells(db, cell_set)
        db.commit()
        print(f"\n✓ 백필 완료. {len(gap_cells)}개 셀 처리, 실제 번호 변경된 배정: {changed}건")

    finally:
        bypass_tenant_filter.reset(tok)


if __name__ == "__main__":
    main()
