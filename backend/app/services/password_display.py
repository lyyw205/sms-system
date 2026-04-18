"""Display-use door passcode variants.

도어락의 실제 비밀번호(Room.door_password) 는 수정하지 않고, 템플릿에서
쓰이는 표시용 변형을 생성한다. 현재는 "랜덤 prefix + 실제 번호" 한 가지만
제공하며, 필요 시 suffix 등 다른 변형을 같은 파일에 나란히 추가한다.

도어락이 "뒷자리 매칭" 방식이라 prefix 가 붙어도 원번호로 해제된다는 점을
이용해, 각 예약자에게 서로 다른 표시 번호를 주어 CCTV/어깨너머 유출을
줄이는 용도다.

Reuse 규칙 (도미토리 공동 투숙, 수동 복수 배정, 연박자 등) 은 저장 레이어
(room_assignment.assign_room) 에서 관리하고, 이 모듈은 순수 생성 함수만
제공한다.
"""
import random


def build_prefixed_password(room) -> str:
    """Room.door_password 앞에 '{random 0-9}0' prefix 를 붙여 반환.

    - door_password 가 빈값이면 빈 문자열 반환
    - door_password 가 비숫자이면 prefix 생략하고 원값 반환
      (도어락이 숫자만 받는 것을 가정한 안전장치)
    """
    base = (room.door_password or "").strip()
    if not base:
        return ""
    if not base.isdigit():
        return base
    return f"{random.randint(0, 9)}0{base}"
