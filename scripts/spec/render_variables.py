#!/usr/bin/env python3
"""변수 전수조사(S2) → 읽기 쉬운 문서 + 커버리지.

  variables/01-db-columns.yaml   기계 추출 (재생성됨)
  variables/02-settings.yaml     기계 추출
  variables/03-constants.yaml    기계 추출
  variables/04-template-vars.yaml 기계 추출
  variables/10-domain-axes.yaml  ← 사람이 쓴 도메인 값 사전 (이것만 편집)
        ↓
  변수명세/*.md
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML 필요:  pip install pyyaml")

REPO = Path(__file__).resolve().parents[2]
VAR = REPO / "docs/plans/refactor/variables"
OUT = REPO / "docs/plans/refactor/변수명세"


def render_axes(data) -> str:
    L = []
    A = L.append
    axes = data.get("axes") or []
    A("# 도메인 값 사전")
    A("")
    A("> `variables/10-domain-axes.yaml` 에서 자동 생성됩니다. **직접 고치지 마세요.**")
    A("")
    A(f"이 시스템에서 **값이 정해져 있는 자리 {len(axes)}개**입니다.")
    A("리팩토링할 때 값 하나라도 빠뜨리면 그 경로가 조용히 죽습니다.")
    A("")
    A("## 목차")
    A("")
    for a in axes:
        anchor = a["축"].replace(" ", "-").replace(".", "").replace("(", "").replace(")", "")
        A(f"- [{a['축']}](#{anchor})")
    A("")
    A("---")
    A("")
    for a in axes:
        A(f"## {a['축']}")
        A("")
        if a.get("정의처"):
            A(f"**값 목록이 있는 곳**: `{a['정의처']}`")
            A("")
        else:
            A("**값 목록이 있는 곳**: 없음 — 코드 곳곳에 흩어져 있음 ⚠️")
            A("")
        if a.get("타입"):
            A(f"**타입**: {a['타입']}")
            A("")
        if a.get("기본값"):
            A(f"**기본값**: {a['기본값']}")
            A("")
        for key in ("값", "값표현", "분류"):
            v0 = a.get(key)
            if not v0:
                continue
            A(f"**{key}**")
            A("")
            if isinstance(v0, dict):
                A("| | 뜻 |")
                A("|---|---|")
                for k, v in v0.items():
                    A(f"| `{k}` | {v} |")
            else:
                A(str(v0))
            A("")
        for key in ("규약", "성질표", "일자별확장", "대상필드", "칸", "연산자"):
            if a.get(key):
                A(f"**{key}**: {a[key]}")
                A("")
        if a.get("함정"):
            A("> ⚠️ **함정**")
            A(">")
            for line in str(a["함정"]).rstrip().split("\n"):
                A(f"> {line}" if line.strip() else ">")
            A("")
        if a.get("주의2"):
            A(f"> 📝 {a['주의2']}")
            A("")
        A("---")
        A("")
    return "\n".join(L)


def render_columns(data) -> str:
    L = []
    A = L.append
    models = data.get("models") or []
    ncol = sum(len(m.get("columns") or []) for m in models)
    A("# DB 컬럼 전수")
    A("")
    A(f"> 기계 추출. 모델 **{len(models)}개 · 컬럼 {ncol}개**")
    A(">")
    A("> `실사용값` 은 코드 전체에서 그 컬럼과 비교·대입되는 문자열 리터럴을 자동 수집한 것입니다.")
    A("> 값이 상수 집합에만 정의된 컬럼(예: `party_type`)은 여기 비어 있고 도메인 값 사전에 있습니다.")
    A("")
    for m in models:
        A(f"## `{m['model']}`" + (f" — `{m.get('table','')}`" if m.get("table") else ""))
        A("")
        if m.get("doc"):
            A(f"{m['doc']}")
            A("")
        A("| 컬럼 | 타입 | 속성 | 설명 | 실사용값 |")
        A("|------|------|------|------|----------|")
        for c in m.get("columns") or []:
            db = f" <sub>(DB: `{c['db_name']}`)</sub>" if c.get("db_name") else ""
            vals = c.get("실사용값") or ""
            if c.get("⚠오탐주의"):
                vals += " ⚠️"
            A(f"| `{c['name']}`{db} | `{c.get('type','')}` | {c.get('attrs','')} "
              f"| {c.get('comment','')} | {vals} |")
        A("")
    return "\n".join(L)


def render_constants(data) -> str:
    L = []
    A = L.append
    cs = data.get("constants") or []
    A("# 모듈 상수 전수")
    A("")
    A(f"> 기계 추출. **{len(cs)}개**. 도메인 값 집합이 여기 정의돼 있습니다.")
    A("")
    A("| 상수 | 위치 | 값 | 설명 |")
    A("|------|------|-----|------|")
    for c in cs:
        val = c["value"]
        if len(val) > 160:
            val = val[:157] + "…"
        A(f"| `{c['name']}` | `{c['module']}` | `{val}` | {c.get('comment','')} |")
    A("")
    return "\n".join(L)


def render_settings(data) -> str:
    L = []
    A = L.append
    ss = data.get("settings") or []
    A("# 환경설정 전수")
    A("")
    A(f"> 기계 추출. **{len(ss)}개**")
    A("")
    A("| 설정 | 타입 | 기본값 | 설명 |")
    A("|------|------|--------|------|")
    for s in ss:
        A(f"| `{s['name']}` | `{s['type']}` | `{s.get('default','')}` | {s.get('comment','')} |")
    A("")
    return "\n".join(L)


def render_tvars(data) -> str:
    L = []
    A = L.append
    vs = data.get("template_variables") or []
    A("# 문자 템플릿 변수 전수")
    A("")
    A(f"> 기계 추출. **{len(vs)}개**. 문자 본문에 `{{{{변수}}}}` 로 쓰입니다.")
    A("")
    A("| 변수 | 설명 | 예시 | 분류 |")
    A("|------|------|------|------|")
    for v in vs:
        A(f"| `{{{{{v['name']}}}}}` | {v.get('description','')} "
          f"| {v.get('example','')} | {v.get('category','')} |")
    A("")
    return "\n".join(L)


RENDER = {
    "10-domain-axes": ("도메인값사전.md", render_axes),
    "01-db-columns": ("DB컬럼.md", render_columns),
    "03-constants": ("모듈상수.md", render_constants),
    "02-settings": ("환경설정.md", render_settings),
    "04-template-vars": ("템플릿변수.md", render_tvars),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for stem, (fname, fn) in RENDER.items():
        p = VAR / f"{stem}.yaml"
        if not p.exists():
            continue
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        (OUT / fname).write_text(fn(data) + "\n", encoding="utf-8")
        made.append(fname)
        print(f"✅ {(OUT / fname).relative_to(REPO)}")
    if not made:
        print("생성된 문서 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
