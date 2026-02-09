"""
Template Variable Definitions and Auto-calculation

Defines all available template variables and provides functions to calculate them.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..db.models import Reservation


# 사용 가능한 템플릿 변수 정의
AVAILABLE_VARIABLES = {
    # 예약자 정보
    "name": {
        "description": "예약자 이름",
        "example": "김철수",
        "category": "reservation"
    },
    "phone": {
        "description": "전화번호",
        "example": "010-1234-5678",
        "category": "reservation"
    },

    # 객실 정보
    "building": {
        "description": "건물 (A, B 등)",
        "example": "A",
        "category": "room"
    },
    "roomNum": {
        "description": "호수 (101, 205 등)",
        "example": "101",
        "category": "room"
    },
    "roomNumber": {
        "description": "전체 객실 번호 (A101 등)",
        "example": "A101",
        "category": "room"
    },
    "roomInfo": {
        "description": "객실 타입 (스탠다드, 디럭스 등)",
        "example": "스탠다드",
        "category": "room"
    },
    "password": {
        "description": "객실 비밀번호",
        "example": "12345",
        "category": "room"
    },

    # 파티 정보
    "priceInfo": {
        "description": "파티 가격 안내",
        "example": "남자 3만원 / 여자 2만원",
        "category": "party"
    },
    "partyTime": {
        "description": "파티 시작 시간",
        "example": "저녁 8시",
        "category": "party"
    },
    "secondPartyTime": {
        "description": "2차 시작 시간",
        "example": "밤 10시",
        "category": "party"
    },
    "totalParticipants": {
        "description": "총 참여 인원",
        "example": "25",
        "category": "party"
    },
    "femaleCount": {
        "description": "여성 참여 인원",
        "example": "12",
        "category": "party"
    },
    "maleCount": {
        "description": "남성 참여 인원",
        "example": "13",
        "category": "party"
    },

    # 날짜/시간
    "date": {
        "description": "예약 날짜",
        "example": "2026-02-09",
        "category": "datetime"
    },
    "time": {
        "description": "예약 시간",
        "example": "14:00",
        "category": "datetime"
    },

    # 기타
    "location": {
        "description": "장소",
        "example": "스테이블 B동 1층 포차",
        "category": "other"
    },
}


def calculate_template_variables(
    reservation: Reservation,
    db: Session,
    date: Optional[str] = None,
    custom_vars: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate all template variables for a reservation

    Args:
        reservation: Reservation object
        db: Database session
        date: Optional date for party statistics
        custom_vars: Custom variables to override defaults

    Returns:
        Dictionary of all calculated variables
    """
    variables = {}

    # 예약자 정보
    variables['name'] = reservation.customer_name or ''
    variables['phone'] = reservation.phone or ''

    # 객실 정보
    if reservation.room_number:
        variables['roomNumber'] = reservation.room_number
        # 건물과 호수 분리 (예: A101 → building=A, roomNum=101)
        if len(reservation.room_number) >= 2:
            variables['building'] = reservation.room_number[0]
            variables['roomNum'] = reservation.room_number[1:]
        else:
            variables['building'] = ''
            variables['roomNum'] = reservation.room_number
    else:
        variables['roomNumber'] = ''
        variables['building'] = ''
        variables['roomNum'] = ''

    variables['roomInfo'] = reservation.room_info or ''
    variables['password'] = reservation.room_password or ''

    # 파티 정보 - 기본값 설정
    variables['priceInfo'] = '남자 3만원 / 여자 2만원\n계좌: 카카오뱅크 3333-12-3456789 (홍길동)'
    variables['partyTime'] = '저녁 8시'
    variables['secondPartyTime'] = '밤 10시'
    variables['location'] = '스테이블 B동 1층 포차'

    # 해당 날짜의 참여자 통계 계산
    target_date = date or reservation.date
    if target_date:
        # 총 참여 인원 (확정된 예약만)
        total_count = db.query(Reservation).filter(
            Reservation.date == target_date,
            Reservation.status.in_(['confirmed', 'completed'])
        ).count()

        # 성별 통계
        female_count = db.query(Reservation).filter(
            Reservation.date == target_date,
            Reservation.status.in_(['confirmed', 'completed']),
            Reservation.gender == '여'
        ).count()

        male_count = total_count - female_count

        variables['totalParticipants'] = str(total_count)
        variables['femaleCount'] = str(female_count)
        variables['maleCount'] = str(male_count)
    else:
        variables['totalParticipants'] = '0'
        variables['femaleCount'] = '0'
        variables['maleCount'] = '0'

    # 날짜/시간
    variables['date'] = reservation.date or ''
    variables['time'] = reservation.time or ''

    # Custom variables로 덮어쓰기
    if custom_vars:
        variables.update(custom_vars)

    return variables


def get_variable_categories() -> Dict[str, list]:
    """
    Get variables grouped by category

    Returns:
        Dictionary with categories as keys and variable lists as values
    """
    categories = {}
    for var_name, var_info in AVAILABLE_VARIABLES.items():
        category = var_info['category']
        if category not in categories:
            categories[category] = []
        categories[category].append({
            'name': var_name,
            'description': var_info['description'],
            'example': var_info['example']
        })
    return categories
