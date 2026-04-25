"""
일반실 booking_count > 1 기존 데이터 split 1회성 마이그레이션.

배경:
  네이버는 한 예약(bookingId)에 객실 N개를 1건으로 보낸다(bookingCount=N).
  그러나 RoomAssignment.UniqueConstraint(reservation_id, date) 가 한 예약-한 방
  모델이라, booking_count>1 일반실은 자동배정에서 1방만 잡히고 나머지가 손실됐다.
  새 코드(naver_sync._split_multi_room_reservations)는 신규 동기화 시 primary +
  sibling N-1 row 로 split 하지만, 이미 DB 에 박혀있는 booking_count>1 일반실 row
  는 split 안 된 채로 남는다. 이 스크립트로 일제 정리.

처리 방식 (운영 정책 확정안):
  - sibling 은 "수동 예약" 과 동일하게 취급
    external_id=NULL, naver_booking_id=NULL, booking_source='naver_split'
  - 인원/금액 균등분할 (floor + 나머지 primary 몰빵 → 합계 보존)
  - cascade 없음: 네이버 측 변경/취소는 primary 만 자동 반영, sibling 은 운영자 수동 처리
  - SMS 중복 발송 방지: primary 의 발송 완료 칩(sent_at NOT NULL)을 sibling 의 동일
    (template_key, date) 칩에 sent_at 복사하여 "이미 발송됨" 마킹

사용법:
  # 1) 먼저 dry-run 으로 변경 사항 확인
  python -m backend.scripts.split_existing_multi_bookings --dry-run

  # 2) 실제 적용 (단일 트랜잭션 — 1건이라도 실패하면 전체 롤백)
  python -m backend.scripts.split_existing_multi_bookings --apply
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from sqlalchemy import select

# Path setup: repo root
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import (  # noqa: E402
    Reservation,
    Room,
    RoomBizItemLink,
    ReservationSmsAssignment,
)
from app.db.tenant_context import bypass_tenant_filter  # noqa: E402


def _build_dorm_biz_set(db) -> set[str]:
    """도미토리 biz_item_id 집합 — split 대상 제외용."""
    rows = (
        db.query(RoomBizItemLink.biz_item_id)
        .join(Room, Room.id == RoomBizItemLink.room_id)
        .filter(Room.is_dormitory == True)  # noqa: E712
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _build_mapped_biz_set(db) -> set[str]:
    """RoomBizItemLink 에 매핑된 모든 biz_item_id (도미토리/일반실 무관).

    매핑 없는 biz_item (예: 차량투어 '미니지프투어', 미등록 상품) 은 정체 불명이라
    split 대상에서 제외 — 운영 사고 방지.
    """
    rows = db.query(RoomBizItemLink.biz_item_id).distinct().all()
    return {r[0] for r in rows}


def _split_counts(total: int, n: int) -> tuple[int, int]:
    """floor + 나머지 primary 몰빵. 반환: (primary_share, sibling_share)."""
    if not total or n <= 1:
        return (total or 0, 0)
    sibling_share = total // n
    primary_share = total - sibling_share * (n - 1)
    return (primary_share, sibling_share)


def _clone_reservation(primary: Reservation, **overrides) -> Reservation:
    """primary 를 복제해서 sibling Reservation 객체 생성. PK/timestamp 는 ORM 자동 처리."""
    sibling = Reservation(
        tenant_id=primary.tenant_id,
        # 식별자: NULL (수동 예약처럼)
        external_id=None,
        naver_booking_id=None,
        # 추적 라벨
        booking_source="naver_split",
        # 분할되는 필드 (overrides 로 주입)
        booking_count=overrides["booking_count"],
        total_price=overrides["total_price"],
        male_count=overrides["male_count"],
        female_count=overrides["female_count"],
        party_size=overrides["party_size"],
        # 나머지는 primary 그대로 복사
        naver_biz_item_id=primary.naver_biz_item_id,
        customer_name=primary.customer_name,
        phone=primary.phone,
        visitor_name=primary.visitor_name,
        visitor_phone=primary.visitor_phone,
        check_in_date=primary.check_in_date,
        check_in_time=primary.check_in_time,
        check_out_date=primary.check_out_date,
        status=primary.status,
        naver_room_type=primary.naver_room_type,
        biz_item_name=primary.biz_item_name,
        booking_options=primary.booking_options,
        special_requests=primary.special_requests,
        confirmed_at=primary.confirmed_at,
        cancelled_at=primary.cancelled_at,
        gender=primary.gender,
        age_group=primary.age_group,
        visit_count=primary.visit_count,
        section=primary.section,
        party_type=primary.party_type,
        # stay_group: sibling 은 chain 후보 제외 (consecutive_stay guard) → NULL
        stay_group_id=None,
        is_long_stay=False,
    )
    return sibling


def _copy_sent_chips(db, primary: Reservation, sibling: Reservation) -> int:
    """primary 의 발송 완료 칩(sent_at NOT NULL)을 sibling 의 동일 (template_key, date) 칩에
    sent_at 복사. sibling 칩이 아직 없으면 새로 생성하면서 sent_at 박음.

    목적: 마이그레이션 후 sibling 에 자동 칩 생성되어 다음 스케줄러 실행 시 이미 발송된 SMS 가
    동일인에게 또 발송되는 위험 방지.

    반환: 복사된 칩 개수.
    """
    sent_chips = (
        db.query(ReservationSmsAssignment)
        .filter(
            ReservationSmsAssignment.reservation_id == primary.id,
            ReservationSmsAssignment.sent_at.isnot(None),
        )
        .all()
    )
    if not sent_chips:
        return 0

    copied = 0
    for chip in sent_chips:
        existing = (
            db.query(ReservationSmsAssignment)
            .filter(
                ReservationSmsAssignment.reservation_id == sibling.id,
                ReservationSmsAssignment.template_key == chip.template_key,
                ReservationSmsAssignment.date == chip.date,
            )
            .first()
        )
        if existing:
            if existing.sent_at is None:
                existing.sent_at = chip.sent_at
                copied += 1
        else:
            db.add(
                ReservationSmsAssignment(
                    tenant_id=sibling.tenant_id,
                    reservation_id=sibling.id,
                    template_key=chip.template_key,
                    date=chip.date,
                    sent_at=chip.sent_at,
                    assigned_by="migration",
                )
            )
            copied += 1
    return copied


def split_one(db, primary: Reservation) -> dict:
    """primary 1건 처리: sibling N-1 생성 + primary 필드 정규화 + 칩 복사. 결과 dict 반환."""
    original_bc = primary.booking_count or 1
    if original_bc <= 1:
        return {"skipped": "booking_count<=1"}
    bc = original_bc

    primary_male, sibling_male = _split_counts(primary.male_count or 0, bc)
    primary_female, sibling_female = _split_counts(primary.female_count or 0, bc)
    primary_price, sibling_price = _split_counts(primary.total_price or 0, bc)
    # party_size: 도미토리 전환/용량 체크 정합성 위해 최소 1 보장하면서 floor 분할
    raw_size = primary.party_size or 1
    sibling_size = max(1, raw_size // bc)
    primary_size = max(1, raw_size - sibling_size * (bc - 1))

    # 1) sibling N-1 개 생성 (먼저 칩 복사 위해 flush 로 ID 확보)
    siblings: List[Reservation] = []
    chips_copied = 0
    for _ in range(bc - 1):
        sibling = _clone_reservation(
            primary,
            booking_count=1,
            total_price=sibling_price,
            male_count=sibling_male,
            female_count=sibling_female,
            party_size=sibling_size,
        )
        db.add(sibling)
        siblings.append(sibling)
    db.flush()  # sibling.id 할당

    # 2) primary 의 발송 완료 칩 → sibling 에 sent_at 복사 (중복 발송 방지)
    for sibling in siblings:
        chips_copied += _copy_sent_chips(db, primary, sibling)

    # 3) primary 정규화: booking_count=1 + 나머지 균등분할 값
    primary.booking_count = 1
    primary.total_price = primary_price
    primary.male_count = primary_male
    primary.female_count = primary_female
    primary.party_size = primary_size

    return {
        "primary_id": primary.id,
        "naver_booking_id": primary.naver_booking_id,
        "customer_name": primary.customer_name,
        "check_in": primary.check_in_date,
        "original_bc": original_bc,
        "siblings_created": len(siblings),
        "sibling_ids": [s.id for s in siblings],
        "chips_copied": chips_copied,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="일반실 booking_count>1 기존 데이터 split")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="변경 사항만 출력 (rollback)")
    group.add_argument("--apply", action="store_true", help="실제 commit")
    args = parser.parse_args()

    bypass_token = bypass_tenant_filter.set(True)
    db = SessionLocal()
    try:
        # 도미토리 biz_item_id 제외 (booking_count 가 인원수 의미)
        dorm_biz = _build_dorm_biz_set(db)
        # RoomBizItemLink 매핑 있는 biz_item 만 대상 (매핑 없는 정체불명 상품 안전 제외)
        mapped_biz = _build_mapped_biz_set(db)
        regular_mapped_biz = mapped_biz - dorm_biz

        # 대상 조회: booking_count>1, 매핑된 일반실, 모든 status
        query = db.query(Reservation).filter(Reservation.booking_count > 1)
        if regular_mapped_biz:
            query = query.filter(Reservation.naver_biz_item_id.in_(regular_mapped_biz))
        else:
            query = query.filter(False)  # 매핑 0건이면 split 대상 없음
        primaries = query.order_by(Reservation.check_in_date).all()

        print(f"\n=== 마이그레이션 대상: {len(primaries)} 건 ===\n")
        print(f"  매핑된 일반실 biz_item: {len(regular_mapped_biz)} 개")
        print(f"  도미토리 제외: {len(dorm_biz)} 개")
        print(f"  매핑 없는 biz_item 제외: {len(set(p.naver_biz_item_id for p in db.query(Reservation).filter(Reservation.booking_count > 1).all()) - mapped_biz)} 개\n")

        results = []
        for primary in primaries:
            try:
                res = split_one(db, primary)
                results.append(res)
                print(
                    f"  #{res['primary_id']:>5} {res['customer_name']:>10} "
                    f"{res['check_in']} bc={res['original_bc']} → "
                    f"sibling {res['siblings_created']}건 (id={res['sibling_ids']}) "
                    f"칩복사 {res['chips_copied']}건"
                )
            except Exception as e:
                print(f"  #{primary.id} FAILED: {e}")
                raise

        total_siblings = sum(r["siblings_created"] for r in results)
        total_chips = sum(r["chips_copied"] for r in results)
        print(f"\n=== 결과 요약 ===")
        print(f"  primary 정규화: {len(results)} 건")
        print(f"  sibling 생성:    {total_siblings} 건")
        print(f"  발송완료 칩 복사: {total_chips} 건 (중복 발송 방지)")

        if args.dry_run:
            db.rollback()
            print("\n[DRY-RUN] 모든 변경 롤백. --apply 옵션으로 실제 적용.\n")
        else:
            db.commit()
            print("\n[APPLY] 모든 변경 commit 완료.\n")
        return 0
    except Exception as e:
        db.rollback()
        print(f"\n[ROLLBACK] 오류 발생, 전체 롤백: {e}\n", file=sys.stderr)
        return 1
    finally:
        db.close()
        bypass_tenant_filter.reset(bypass_token)


if __name__ == "__main__":
    sys.exit(main())
