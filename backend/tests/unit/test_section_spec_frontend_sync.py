"""프론트 미러 명세서 ↔ 백엔드 명세서 drift-guard.

frontend/src/lib/sectionSpec.ts 의 SECTION_SPEC(label/draggable)이
백엔드 section_registry 와 정확히 일치함을 강제한다.
두 표(Python/TS)가 어긋나면 이 테스트가 실패한다 — 미러의 유일한 위험(동기화 깨짐)을 막는 그물.

공유 속성만 비교: label, draggable.
(zone/색상/accept 등 프론트 고유 속성은 백엔드에 없으므로 대조 대상 아님.)
"""
import re
from pathlib import Path

import pytest

from app.services.section_registry import SECTIONS

_FRONTEND_SPEC = Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "sectionSpec.ts"
# 예: `  room: { label: '객실', draggable: true },`
_ENTRY_RE = re.compile(
    r"(\w+):\s*\{\s*label:\s*'([^']*)',\s*draggable:\s*(true|false)\s*\}"
)


def _parse_frontend_spec() -> dict[str, tuple[str, bool]]:
    text = _FRONTEND_SPEC.read_text(encoding="utf-8")
    out: dict[str, tuple[str, bool]] = {}
    for key, label, drag in _ENTRY_RE.findall(text):
        out[key] = (label, drag == "true")
    return out


@pytest.mark.skipif(not _FRONTEND_SPEC.exists(), reason="frontend sectionSpec.ts 없음")
def test_frontend_spec_keys_match_backend():
    fe = _parse_frontend_spec()
    assert set(fe.keys()) == set(SECTIONS.keys()), (
        f"section 키 불일치 — 백엔드 {set(SECTIONS)} vs 프론트 {set(fe)}"
    )


@pytest.mark.skipif(not _FRONTEND_SPEC.exists(), reason="frontend sectionSpec.ts 없음")
def test_frontend_label_and_draggable_match_backend():
    fe = _parse_frontend_spec()
    assert fe, "프론트 sectionSpec.ts 파싱 실패 (포맷 변경?)"
    for section, spec in SECTIONS.items():
        fe_label, fe_drag = fe[section]
        assert fe_label == spec.label, f"[{section}] label drift: 백엔드 {spec.label} vs 프론트 {fe_label}"
        assert fe_drag == spec.draggable, f"[{section}] draggable drift: 백엔드 {spec.draggable} vs 프론트 {fe_drag}"
