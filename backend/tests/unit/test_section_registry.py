"""section_registry 특성화 테스트.

명세서 값이 현재 코드 곳곳의 하드코딩과 **정확히 일치**함을 못박는다.
마이그레이션(호출처를 명세서 조회로 교체) 시 이 테스트가 동작 동등성을 보장한다.
각 assert 의 기댓값은 현재 소스의 리터럴에서 그대로 옮겨온 것 (주석에 출처 명시).
"""
from app.services.section_registry import (
    SECTIONS,
    spec_for,
    assignable_sections,
    non_assignable_sections,
    non_lodging_sections,
    naver_inbound_sections,
    has_stay,
    is_draggable,
    inherits_default_party,
    label_for,
)


def test_assignable_matches_room_auto_assign_notin():
    # room_auto_assign.py:232 → Reservation.section.notin_(['party','unstable','activity'])
    assert set(non_assignable_sections()) == {'party', 'unstable', 'activity'}
    assert set(assignable_sections()) == {'room', 'unassigned'}


def test_non_lodging_matches_stats_exclusion():
    # variables/template_scheduler/dashboard/event_sms/filters → section != 'activity'
    assert set(non_lodging_sections()) == {'activity'}


def test_naver_inbound_matches_section_hint_whitelist():
    # naver_sync.py:688 → section_hint in ('party','room','unstable','activity')
    assert set(naver_inbound_sections()) == {'party', 'room', 'unstable', 'activity'}


def test_has_stay_false_only_for_activity():
    # consecutive_stay.py:338 / reservations_stay.py:176 → activity 연박·연장 거부
    assert {s for s in SECTIONS if not has_stay(s)} == {'activity'}


def test_draggable_false_only_for_activity():
    # GuestRow.tsx:91 / MobileGuestRow.tsx:102 → disabled when zone === 'activity'
    assert {s for s in SECTIONS if not is_draggable(s)} == {'activity'}


def test_default_party_inherit_false_only_for_activity():
    # naver_sync.py:694 → default_pt 적용 조건에 section != 'activity'
    assert {s for s in SECTIONS if not inherits_default_party(s)} == {'activity'}


def test_null_and_unknown_section_fall_back_to_unassigned():
    # reservations.py:223 'section or "unassigned"' + 통계 coalesce(section,'') 방어 계승
    assert spec_for(None) is SECTIONS['unassigned']
    assert spec_for('') is SECTIONS['unassigned']
    assert spec_for('something_unknown') is SECTIONS['unassigned']


def test_labels_match_section_labels():
    # reservations.py:292 section_labels
    assert label_for('room') == '객실'
    assert label_for('unassigned') == '미배정'
    assert label_for('party') == '파티만'
    assert label_for('unstable') == '언스테이블'
    assert label_for('activity') == '액티비티'
