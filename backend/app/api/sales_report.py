"""
Sales Report API - 매출 조회 (현장판매 + 네이버 객실)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.api.deps import get_tenant_scoped_db
from app.auth.dependencies import get_current_user
from app.db.models import Reservation, ReservationStatus, OnsiteSale, User

router = APIRouter(prefix="/api/sales-report", tags=["sales-report"])


class SalesItem(BaseModel):
    date: str
    category: str  # 'onsite' | 'naver'
    product_name: str
    amount: int
    count: int


class SalesSummary(BaseModel):
    total: int
    onsite: int
    naver: int


class FilterOptions(BaseModel):
    biz_item_names: List[str]
    onsite_item_names: List[str]


class SalesReportResponse(BaseModel):
    summary: SalesSummary
    items: List[SalesItem]
    filter_options: FilterOptions


@router.get("", response_model=SalesReportResponse)
async def get_sales_report(
    date_from: str = Query(..., description="시작일 YYYY-MM-DD"),
    date_to: str = Query(..., description="종료일 YYYY-MM-DD"),
    category: Optional[str] = Query(None, description="onsite | naver"),
    biz_item_name: Optional[str] = Query(None, description="네이버 상품명 필터"),
    item_name: Optional[str] = Query(None, description="현장판매 품명 필터"),
    group_by: str = Query("day", description="day | month"),
    db: Session = Depends(get_tenant_scoped_db),
    current_user: User = Depends(get_current_user),
):
    items: List[SalesItem] = []

    # --- 현장판매 집계 ---
    if category is None or category == "onsite":
        onsite_query = db.query(OnsiteSale).filter(
            OnsiteSale.date >= date_from,
            OnsiteSale.date <= date_to,
        )
        if item_name:
            onsite_query = onsite_query.filter(OnsiteSale.item_name == item_name)

        onsite_rows = onsite_query.all()

        # 그룹핑
        onsite_groups: dict[str, dict[str, dict]] = {}
        for row in onsite_rows:
            date_key = row.date[:7] if group_by == "month" else row.date
            product = row.item_name
            key = f"{date_key}|{product}"
            if key not in onsite_groups:
                onsite_groups[key] = {"date": date_key, "product_name": product, "amount": 0, "count": 0}
            onsite_groups[key]["amount"] += row.amount
            onsite_groups[key]["count"] += 1

        for g in onsite_groups.values():
            items.append(SalesItem(
                date=g["date"],
                category="onsite",
                product_name=g["product_name"],
                amount=g["amount"],
                count=g["count"],
            ))

    # --- 네이버 객실 매출 집계 ---
    if category is None or category == "naver":
        naver_query = db.query(Reservation).filter(
            Reservation.check_in_date >= date_from,
            Reservation.check_in_date <= date_to,
            Reservation.status == ReservationStatus.CONFIRMED,
            Reservation.total_price.isnot(None),
            Reservation.total_price > 0,
            Reservation.booking_source == "naver",
        )
        if biz_item_name:
            naver_query = naver_query.filter(Reservation.biz_item_name == biz_item_name)

        naver_rows = naver_query.all()

        naver_groups: dict[str, dict] = {}
        for row in naver_rows:
            date_key = row.check_in_date[:7] if group_by == "month" else row.check_in_date
            product = row.biz_item_name or "미분류"
            key = f"{date_key}|{product}"
            if key not in naver_groups:
                naver_groups[key] = {"date": date_key, "product_name": product, "amount": 0, "count": 0}
            naver_groups[key]["amount"] += row.total_price
            naver_groups[key]["count"] += 1

        for g in naver_groups.values():
            items.append(SalesItem(
                date=g["date"],
                category="naver",
                product_name=g["product_name"],
                amount=g["amount"],
                count=g["count"],
            ))

    # 정렬: 날짜 → 카테고리 → 상품명
    items.sort(key=lambda x: (x.date, x.category, x.product_name))

    # 요약
    onsite_total = sum(i.amount for i in items if i.category == "onsite")
    naver_total = sum(i.amount for i in items if i.category == "naver")

    # 필터 옵션 (해당 기간 내 존재하는 상품명 목록)
    all_onsite = db.query(OnsiteSale.item_name).filter(
        OnsiteSale.date >= date_from, OnsiteSale.date <= date_to,
    ).distinct().all()
    all_naver = db.query(Reservation.biz_item_name).filter(
        Reservation.check_in_date >= date_from,
        Reservation.check_in_date <= date_to,
        Reservation.status == ReservationStatus.CONFIRMED,
        Reservation.total_price.isnot(None),
        Reservation.booking_source == "naver",
        Reservation.biz_item_name.isnot(None),
    ).distinct().all()

    return SalesReportResponse(
        summary=SalesSummary(
            total=onsite_total + naver_total,
            onsite=onsite_total,
            naver=naver_total,
        ),
        items=items,
        filter_options=FilterOptions(
            biz_item_names=sorted([r[0] for r in all_naver if r[0]]),
            onsite_item_names=sorted([r[0] for r in all_onsite if r[0]]),
        ),
    )
