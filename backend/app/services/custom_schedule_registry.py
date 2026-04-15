"""
custom_schedule_registry.py — 커스텀 스케줄 로직 레지스트리

새 커스텀 로직 추가 시 이 파일의 CUSTOM_SCHEDULE_TYPES에 등록하면
API를 통해 프론트엔드 드롭다운에 자동으로 반영됩니다.
"""

# 커스텀 스케줄 타입 레지스트리
# key: custom_type 값 (DB에 저장됨)
# label: UI에 표시되는 한글 라벨
CUSTOM_SCHEDULE_TYPES = {
    "surcharge_1": "추가 인원 1인 초과",
    "surcharge_2": "추가 인원 2인 초과",
    "surcharge_3": "추가 인원 3인 초과",
    "surcharge_4": "추가 인원 4인 초과",
}


def get_custom_types() -> list[dict]:
    """프론트엔드 드롭다운용 커스텀 타입 목록 반환."""
    return [
        {"value": key, "label": label}
        for key, label in CUSTOM_SCHEDULE_TYPES.items()
    ]
