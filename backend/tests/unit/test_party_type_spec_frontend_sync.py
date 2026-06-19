"""프론트 party_type 미러(partyTypeSpec.ts) ↔ 백엔드 party_type.PARTY_JOINED_TYPES drift-guard.

frontend/src/lib/partyTypeSpec.ts 의 PARTY_JOINED_TYPES Set 이
백엔드 party_type.PARTY_JOINED_TYPES 와 정확히 일치함을 강제한다.
두 표(Python/TS)가 어긋나면 이 테스트가 실패한다 — 세 페이지(RoomAssignment/PartyCheckin/
SummaryCards) 인원 동기화의 유일한 위험(동기 깨짐)을 막는 그물.
(test_section_spec_frontend_sync.py 와 동일 패턴.)
"""
import re
from pathlib import Path

import pytest

from app.services.party_type import PARTY_JOINED_TYPES

_FRONTEND_SPEC = Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "partyTypeSpec.ts"
# 예: `export const PARTY_JOINED_TYPES = new Set(['1', '2', '2차만']);`
_SET_RE = re.compile(r"PARTY_JOINED_TYPES\s*=\s*new Set\(\[([^\]]*)\]\)")
_ITEM_RE = re.compile(r"'([^']*)'")


def _parse_frontend_set() -> set[str]:
    text = _FRONTEND_SPEC.read_text(encoding="utf-8")
    m = _SET_RE.search(text)
    if not m:
        return set()
    return set(_ITEM_RE.findall(m.group(1)))


@pytest.mark.skipif(not _FRONTEND_SPEC.exists(), reason="frontend partyTypeSpec.ts 없음")
def test_frontend_party_joined_set_matches_backend():
    fe = _parse_frontend_set()
    assert fe, "프론트 partyTypeSpec.ts 파싱 실패 (포맷 변경?)"
    assert fe == set(PARTY_JOINED_TYPES), (
        f"PARTY_JOINED_TYPES drift — 백엔드 {set(PARTY_JOINED_TYPES)} vs 프론트 {fe}"
    )
