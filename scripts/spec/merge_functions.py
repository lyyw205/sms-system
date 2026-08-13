#!/usr/bin/env python3
"""함수 골격(기계 추출) + 의미 주석(사람 작성) → 읽기 쉬운 문서 + 진행률.

  functions/*.yaml   기계 추출 골격 — 재생성됨. 절대 손대지 말 것
  semantics/*.yaml   사람이 쓴 역할/주의/등급 — 이것만 편집
        ↓ merge
  함수명세/*.md       읽기 쉬운 통합 문서
  함수명세/_진행률.md  전수조사 커버리지

semantics 형식:
    module: services/stay_logic.py
    fns:
      is_single_day_stay:
        역할: 당일 1박인지 판정하는 유일한 기준
        등급: D
        주의: co<ci 도 연박으로 취급 — 현행 보존
        핵심: true
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML 필요:  pip install pyyaml")

REPO = Path(__file__).resolve().parents[2]
FUNCS = REPO / "docs/plans/refactor/functions"
SEM = REPO / "docs/plans/refactor/semantics"
OUT = REPO / "docs/plans/refactor/함수명세"

GRADE = {
    "D": ("🔵", "업무 규칙"),
    "G": ("🛡", "보호 장치"),
    "L": ("🕰", "옛 데이터 호환"),
    "N": ("✔", "존재 확인"),
    "I": ("⚙", "기술 처리"),
}


def load_semantics() -> dict[str, dict]:
    """{module: {fnname: {...}}}"""
    out: dict[str, dict] = {}
    if not SEM.exists():
        return out
    for p in sorted(SEM.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        mods = data if isinstance(data, list) else [data]
        for m in mods:
            if not m or "module" not in m:
                continue
            out.setdefault(m["module"], {}).update(m.get("fns") or {})
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sem = load_semantics()

    tot = Counter()
    per_mod = []
    grade_count = Counter()
    cores, cautions = [], []

    for p in sorted(FUNCS.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        mod = data["module"]
        fns = data.get("fns") or []
        msem = sem.get(mod, {})

        done = 0
        L = []
        A = L.append
        A(f"# {mod}")
        A("")
        A(f"> 골격 자동생성 + 의미 수동작성 병합. 원본 코드 **{data['loc']}줄 · 함수 {len(fns)}개**")
        if data.get("module_doc"):
            A(">")
            A(f"> {data['module_doc'][:400]}")
        A("")

        for f in fns:
            raw = f["name"].strip()
            key = raw.replace("↳", "").strip()
            s = msem.get(key) or msem.get(raw) or {}
            if s.get("역할"):
                done += 1
                grade_count[s.get("등급", "?")] += 1
                if s.get("핵심"):
                    cores.append((mod, key, s.get("역할", "")))
                if s.get("주의"):
                    cautions.append((mod, key, s["주의"]))

            ico, glab = GRADE.get(s.get("등급", ""), ("", ""))
            star = "⭐ " if s.get("핵심") else ""
            mark = "" if s.get("역할") else " 🔺미작성"
            A(f"## {star}{ico} `{key}`{mark}")
            A("")
            if s.get("역할"):
                A(f"**{s['역할']}**")
                A("")
            A(f"<sub>`{mod}:{f['line']}` · {f['loc']}줄"
              + (f" · {glab}" if glab else "")
              + (" · async" if f.get("is_async") else "") + "</sub>")
            A("")
            A(f"```python\n{key}{f['sig']}\n```")
            A("")
            if f.get("doc"):
                A(f"> 원본 주석: {f['doc'][:500]}")
                A("")
            if s.get("주의"):
                A(f"> ⚠️ **주의** — {s['주의']}")
                A("")
            if s.get("순서"):
                A(f"> 🔴 **순서 의존** — {s['순서']}")
                A("")
            for label, field in (("차단/조기반환", "guards"), ("분기", "branches"),
                                 ("삼항", "ternaries"), ("예외 발생", "raises"),
                                 ("예외 처리", "excepts")):
                if f.get(field):
                    A(f"**{label}** ({len(f[field])})")
                    A("")
                    for x in f[field]:
                        A(f"- `{x}`")
                    A("")
            if f.get("diag"):
                A("**진단로그**: " + ", ".join(f"`{x}`" for x in f["diag"]))
                A("")
            if f.get("writes"):
                A("**쓰는 데이터**: " + ", ".join(f"`{x}`" for x in f["writes"]))
                A("")
            if f.get("effects"):
                A("**부작용**: " + ", ".join(f"`{x}`" for x in f["effects"]))
                A("")
            if f.get("calls"):
                A("<sub>호출: " + ", ".join(f"`{x}`" for x in f["calls"][:30]) + "</sub>")
                A("")

        (OUT / p.name.replace(".yaml", ".md")).write_text("\n".join(L) + "\n", encoding="utf-8")
        tot["fns"] += len(fns)
        tot["done"] += done
        per_mod.append((mod, len(fns), done, data["loc"]))

    # ── 진행률 ─────────────────────────────────────────
    L = []
    A = L.append
    pct = tot["done"] * 100 // max(tot["fns"], 1)
    A("# 전수조사 진행률")
    A("")
    A(f"> `scripts/spec/merge_functions.py` 자동 생성")
    A("")
    A(f"## 전체 — **{tot['done']} / {tot['fns']} 함수 ({pct}%)**")
    A("")
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    A(f"`{bar}` {pct}%")
    A("")
    if grade_count:
        A("### 등급 분포 (작성분)")
        A("")
        A("| 등급 | 뜻 | 개수 |")
        A("|---|---|---:|")
        for g, (ico, lab) in GRADE.items():
            if grade_count.get(g):
                A(f"| {ico} {g} | {lab} | {grade_count[g]} |")
        A("")
        dg = grade_count.get("D", 0) + grade_count.get("G", 0)
        A(f"**반드시 옮겨야 하는 함수 = D + G = {dg}개**")
        A("")

    A("## 모듈별")
    A("")
    A("| 모듈 | 코드 | 함수 | 완료 | |")
    A("|------|-----:|-----:|-----:|---|")
    for mod, n, d, loc in sorted(per_mod, key=lambda x: (x[2] / max(x[1], 1), -x[1])):
        p2 = d * 100 // max(n, 1)
        icon = "✅" if p2 == 100 else ("🟡" if p2 else "⬜")
        A(f"| `{mod}` | {loc} | {n} | {d} ({p2}%) | {icon} |")
    A("")

    if cores:
        A("## ⭐ 핵심 표시된 함수")
        A("")
        for mod, fn, role in cores:
            A(f"- **`{fn}`** — {role}  <sub>{mod}</sub>")
        A("")
    if cautions:
        A("## ⚠️ 옮길 때 깨지기 쉬운 것")
        A("")
        for mod, fn, c in cautions:
            A(f"- **`{fn}`** — {c}  <sub>{mod}</sub>")
        A("")

    (OUT / "_진행률.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"✅ {OUT.relative_to(REPO)}/  ({len(per_mod)} 모듈)")
    print(f"   진행률 {tot['done']}/{tot['fns']} ({pct}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
