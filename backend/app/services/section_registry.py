"""Reservation.section 행동 명세서 — single source of truth.

코드 곳곳(~30곳)에 흩어져 있던 "어느 section 이 어떤 성질인가" 하드코딩을 한 곳에 모은다.
각 값은 **기존 코드의 하드코딩과 정확히 일치**하도록 채워졌다 (동작 불변 — 판단의 위치만 이동).

기존 하드코딩 대응:
  - assignable           ← room_auto_assign.py 의 section.notin_(['party','unstable','activity'])
                           + room_assignment.assign_room 의 activity 거부
  - lodging_guest        ← variables/template_scheduler/dashboard/event_sms/filters 의 section != 'activity'
                           (숙박 인원 통계 SUM / SMS 브로드캐스트 기본 대상)
  - has_stay             ← consecutive_stay / reservations_stay 의 activity 연박·연장 거부
  - draggable            ← GuestRow 의 zone === 'activity' 드래그 비활성 (프론트 미러)
  - default_party_inherit← naver_sync 의 default_party_type 상속 시 section != 'activity'
  - naver_inbound        ← naver_sync.py 의 section_hint in ('party','room','unstable','activity')
  - label                ← reservations.py 의 section_labels

⚠️ 이 명세서가 담지 않는 것 — section "단독"이 아니라 오버레이(다른 플래그)와 결합되는 로직.
   호출처에 **그대로 유지**한다 (명세서로 옮기면 방어 로직을 잃는다):
     1. room_id 우선     — 배정된 예약(room_id 있음)은 section 무관 'assigned' 취급
     2. unstable_party   — 비-unstable 예약도 unstable_party=true / daily unstable 이면 언스 zone 에 복사·집계
                           (useReservationsData / filters._condition_simple_assignment / party_checkin)
     3. party_type 오버레이 — 어느 section 이든 effective party_type ∈ {1,2,2차만} 이면 파티 명단/통계 포함
     4. sectionOverrides — 프론트 클라이언트 즉시성 오버라이드 (override ?? section)
     5. filters room 카테고리 modifier — buildings / include_unassigned
   이들은 section 속성이 아니라 '결합 로직'이므로 명세서 + 기존 위치 **둘 다** 존재한다.

마이그레이션은 점진적으로: 이 모듈 추가(동작 0) → 호출처를 1곳씩 교체(각각 no-op, 테스트로 검증) → 옛 하드코딩 제거.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SectionSpec:
    label: str                    # UI 라벨 (section_labels)
    assignable: bool              # 객실 자동/수동 배정 대상인가
    lodging_guest: bool           # 숙박 인원 — 통계 SUM / SMS 브로드캐스트 기본 대상인가
    has_stay: bool                # 체크아웃/연박 개념이 있나 (extend / 연박묶기 가능)
    draggable: bool               # 프론트 객실 드래그 가능한가
    default_party_inherit: bool   # NaverBizItem.default_party_type 자동상속을 받나
    naver_inbound: bool           # 네이버 section_hint 로 인입 가능한 값인가


# 값은 현 코드 하드코딩과 1:1 일치. 바꾸면 동작이 바뀌므로 변경 시 특성화 테스트 동반 필수.
SECTIONS: dict[str, SectionSpec] = {
    'room':       SectionSpec('객실',      assignable=True,  lodging_guest=True,  has_stay=True,  draggable=True,  default_party_inherit=True,  naver_inbound=True),
    'unassigned': SectionSpec('미배정',    assignable=True,  lodging_guest=True,  has_stay=True,  draggable=True,  default_party_inherit=True,  naver_inbound=False),
    'party':      SectionSpec('파티만',    assignable=False, lodging_guest=True,  has_stay=True,  draggable=True,  default_party_inherit=True,  naver_inbound=True),
    'unstable':   SectionSpec('언스테이블', assignable=False, lodging_guest=True,  has_stay=True,  draggable=True,  default_party_inherit=True,  naver_inbound=True),
    'activity':   SectionSpec('액티비티',   assignable=False, lodging_guest=False, has_stay=False, draggable=False, default_party_inherit=False, naver_inbound=True),
}

# NULL / 빈문자열 / 미지의 section → 'unassigned' 동작 계승
# (reservations.py 'section or "unassigned"' + 통계의 coalesce(section,'') 방어와 동일)
DEFAULT_SECTION = 'unassigned'


def spec_for(section: str | None) -> SectionSpec:
    """section 의 명세 반환. NULL/빈값/미지 → unassigned 명세 (기존 fallback 계승)."""
    return SECTIONS.get(section or DEFAULT_SECTION, SECTIONS[DEFAULT_SECTION])


# ── 집합 헬퍼 (SQL .in_() / .notin_() 에 사용) ──
def assignable_sections() -> list[str]:
    return [s for s, v in SECTIONS.items() if v.assignable]


def non_assignable_sections() -> list[str]:
    """자동/수동 배정 제외 대상 = room_auto_assign 의 notin_ 리스트."""
    return [s for s, v in SECTIONS.items() if not v.assignable]


def lodging_sections() -> list[str]:
    return [s for s, v in SECTIONS.items() if v.lodging_guest]


def non_lodging_sections() -> list[str]:
    """숙박 통계/브로드캐스트에서 제외할 section (현재 = activity)."""
    return [s for s, v in SECTIONS.items() if not v.lodging_guest]


def naver_inbound_sections() -> tuple[str, ...]:
    """naver_sync section_hint 화이트리스트."""
    return tuple(s for s, v in SECTIONS.items() if v.naver_inbound)


# ── 단건 술어 ──
def is_assignable(section: str | None) -> bool:
    return spec_for(section).assignable


def is_lodging_guest(section: str | None) -> bool:
    return spec_for(section).lodging_guest


def has_stay(section: str | None) -> bool:
    return spec_for(section).has_stay


def is_draggable(section: str | None) -> bool:
    return spec_for(section).draggable


def inherits_default_party(section: str | None) -> bool:
    return spec_for(section).default_party_inherit


def label_for(section: str | None) -> str:
    return spec_for(section).label
