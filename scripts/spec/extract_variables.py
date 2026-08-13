#!/usr/bin/env python3
"""변수·도메인값 전수 추출 (S2).

함수 전수조사(extract_functions.py)와 같은 원칙:
  기계로 먼저 빠짐없이 뽑고, 그 위에 사람이 의미를 얹는다.

추출 항목
  1. DB 컬럼      — models.py 의 모든 Column (타입/nullable/기본값/실제DB명/주석)
  2. 실사용 값    — 코드 전체에서 그 컬럼과 비교되는 **문자열 리터럴 전수**
                    (`x.col == 'v'` / `.in_(['a','b'])` / `col='v'` / dict key)
  3. 설정값       — config.py Settings 필드 (환경변수)
  4. 상수 집합    — 모듈 레벨 frozenset/set/tuple/dict/list 리터럴
  5. 템플릿 변수  — AVAILABLE_VARIABLES

출력: docs/plans/refactor/variables/*.yaml
사용: python scripts/spec/extract_variables.py [--stats]
"""
from __future__ import annotations

import ast
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "backend" / "app"
OUT = REPO / "docs/plans/refactor/variables"


def esc(s: str) -> str:
    s = str(s).replace("\\", "\\\\").replace('"', '\\"')
    return s.replace("\n", " ").replace("\r", "").replace("\t", " ")


def short(s: str, n: int = 200) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# 1. DB 컬럼
# ---------------------------------------------------------------------------
def extract_columns():
    src = (APP / "db" / "models.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    tree = ast.parse(src)
    models = []

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        table = None
        cols = []
        docstring = ast.get_docstring(node)
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]
                name = t.id if isinstance(t, ast.Name) else None
                if name == "__tablename__" and isinstance(stmt.value, ast.Constant):
                    table = stmt.value.value
                    continue
                if not name or not isinstance(stmt.value, ast.Call):
                    continue
                fn = stmt.value.func
                fname = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                if fname not in ("Column", "relationship"):
                    continue
                if fname == "relationship":
                    cols.append({"name": name, "kind": "relationship"})
                    continue
                # Column(...)
                db_name = None
                ctype = None
                for i, a in enumerate(stmt.value.args):
                    if i == 0 and isinstance(a, ast.Constant) and isinstance(a.value, str):
                        db_name = a.value
                    elif ctype is None:
                        ctype = short(ast.unparse(a), 60)
                kw = {}
                for k in stmt.value.keywords:
                    if k.arg:
                        kw[k.arg] = short(ast.unparse(k.value), 60)
                # inline comment
                comment = ""
                ln = lines[stmt.lineno - 1]
                if "#" in ln:
                    comment = ln.split("#", 1)[1].strip()
                cols.append({
                    "name": name, "kind": "column", "db_name": db_name,
                    "type": ctype, "kw": kw, "comment": comment, "line": stmt.lineno,
                })
        if table or cols:
            models.append({"model": node.name, "table": table,
                           "doc": short(docstring or "", 200), "cols": cols,
                           "line": node.lineno})
    return models


# ---------------------------------------------------------------------------
# 2. 실사용 문자열 값 — 컬럼명별
# ---------------------------------------------------------------------------
# 모델 컬럼명이지만 일반 kwarg 로도 흔히 쓰여 오탐이 많은 이름
NOISY = {
    "id", "name", "title", "detail", "description", "status", "date", "hour",
    "minute", "count", "content", "category", "created_at", "updated_at",
    "phone", "message", "error", "value", "key", "type", "level", "reason",
}


def extract_used_values(col_names: set[str]):
    """코드 전체에서 각 컬럼명과 비교/대입되는 문자열 리터럴을 모은다.

    지역변수 별칭까지 추적한다:
        tm = schedule.target_mode
        if tm == 'last_night':      ← 이것도 target_mode 의 값으로 집계
    """
    used: dict[str, Counter] = defaultdict(Counter)
    where: dict[str, set] = defaultdict(set)

    for p in sorted(APP.rglob("*.py")):
        if "_future" in p.parts or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(APP).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        # ── 지역변수 별칭 수집: var = <expr>.col  (or ... or 폴백 포함) ──
        alias: dict[str, str] = {}

        def _cols_in(expr):
            found = []
            for sub in ast.walk(expr):
                if isinstance(sub, ast.Attribute) and sub.attr in col_names:
                    found.append(sub.attr)
            return found

        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                    and isinstance(n.targets[0], ast.Name):
                cols = _cols_in(n.value)
                if len(set(cols)) == 1:
                    alias[n.targets[0].id] = cols[0]

        def attr_name(node):
            """x.col → 'col' · 지역변수 별칭 → 원래 컬럼명"""
            if isinstance(node, ast.Attribute):
                return node.attr
            if isinstance(node, ast.Name) and node.id in alias:
                return alias[node.id]
            return None

        for n in ast.walk(tree):
            # a.col == 'v'  /  a.col != 'v'  /  a.col in ('a','b')
            if isinstance(n, ast.Compare):
                lname = attr_name(n.left)
                if lname in col_names:
                    for comp in n.comparators:
                        for lit in _literals(comp):
                            used[lname][lit] += 1
                            where[lname].add(rel)
                # 'v' == a.col
                for comp in n.comparators:
                    rname = attr_name(comp)
                    if rname in col_names:
                        for lit in _literals(n.left):
                            used[rname][lit] += 1
                            where[rname].add(rel)
            # a.col.in_([...])
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr in ("in_", "notin_", "contains", "like", "startswith"):
                base = n.func.value
                cname = attr_name(base)
                if cname in col_names:
                    for a in n.args:
                        for lit in _literals(a):
                            used[cname][lit] += 1
                            where[cname].add(rel)
            # Model(col='v') / dict {'col': 'v'}
            elif isinstance(n, ast.keyword) and n.arg in col_names:
                for lit in _literals(n.value):
                    used[n.arg][lit] += 1
                    where[n.arg].add(rel)
            elif isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values):
                    if isinstance(k, ast.Constant) and k.value in col_names:
                        for lit in _literals(v):
                            used[k.value][lit] += 1
                            where[k.value].add(rel)
            # setattr 대입: a.col = 'v'
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    tn = attr_name(t)
                    if tn in col_names:
                        for lit in _literals(n.value):
                            used[tn][lit] += 1
                            where[tn].add(rel)
    return used, where


def _literals(node):
    """표현식에서 문자열 리터럴을 뽑는다 (리스트/튜플/집합 포함)."""
    out = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        out.append(node.value)
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for e in node.elts:
            out.extend(_literals(e))
    return [x for x in out if x != "" or True]


# ---------------------------------------------------------------------------
# 3. Settings 필드
# ---------------------------------------------------------------------------
def extract_settings():
    src = (APP / "config.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    tree = ast.parse(src)
    fields = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    comment = ""
                    ln = lines[stmt.lineno - 1]
                    if "#" in ln:
                        comment = ln.split("#", 1)[1].strip()
                    fields.append({
                        "name": stmt.target.id,
                        "type": short(ast.unparse(stmt.annotation), 40),
                        "default": short(ast.unparse(stmt.value), 60) if stmt.value else None,
                        "comment": comment,
                        "line": stmt.lineno,
                    })
    return fields


# ---------------------------------------------------------------------------
# 4. 모듈 레벨 상수 집합
# ---------------------------------------------------------------------------
def extract_constants():
    out = []
    for p in sorted(APP.rglob("*.py")):
        if "_future" in p.parts or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(APP).as_posix()
        src = p.read_text(encoding="utf-8")
        lines = src.splitlines()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in tree.body:
            target = None
            value = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                target, value = node.targets[0].id, node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target, value = node.target.id, node.value
            if not target or value is None:
                continue
            if not re.match(r"^_?[A-Z][A-Z0-9_]*$", target):
                continue
            try:
                rendered = short(ast.unparse(value), 400)
            except Exception:
                continue
            comment = ""
            ln = lines[node.lineno - 1]
            if "#" in ln and not ln.strip().startswith("#"):
                comment = ln.split("#", 1)[1].strip()
            out.append({"module": rel, "name": target, "value": rendered,
                        "comment": comment, "line": node.lineno})
    return out


# ---------------------------------------------------------------------------
# 5. 템플릿 변수
# ---------------------------------------------------------------------------
def extract_template_vars():
    src = (APP / "templates" / "variables.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "AVAILABLE_VARIABLES" and isinstance(node.value, ast.Dict):
            out = []
            for k, v in zip(node.value.keys, node.value.values):
                if not isinstance(k, ast.Constant):
                    continue
                info = {}
                if isinstance(v, ast.Dict):
                    for kk, vv in zip(v.keys, v.values):
                        if isinstance(kk, ast.Constant) and isinstance(vv, ast.Constant):
                            info[kk.value] = vv.value
                out.append({"name": k.value, **info})
            return out
    return []


# ---------------------------------------------------------------------------
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    models = extract_columns()
    col_names = {c["name"] for m in models for c in m["cols"] if c["kind"] == "column"}
    used, where = extract_used_values(col_names)
    settings = extract_settings()
    constants = extract_constants()
    tvars = extract_template_vars()

    # ---- 컬럼 ----
    L = ["# DB 컬럼 전수 (기계 추출) — `역할:`/`값의미:` 는 사람이 채운다", "models:"]
    for m in models:
        L.append(f'  - model: "{esc(m["model"])}"')
        if m["table"]:
            L.append(f'    table: "{esc(m["table"])}"')
        if m["doc"]:
            L.append(f'    doc: "{esc(m["doc"])}"')
        L.append(f"    line: {m['line']}")
        L.append("    columns:")
        for c in m["cols"]:
            if c["kind"] != "column":
                continue
            L.append(f'      - name: "{esc(c["name"])}"')
            if c.get("db_name"):
                L.append(f'        db_name: "{esc(c["db_name"])}"   # 실제 DB 컬럼명이 다름')
            L.append(f'        type: "{esc(c["type"])}"')
            kw = c["kw"]
            flags = []
            for k in ("nullable", "default", "server_default", "index", "unique", "primary_key"):
                if k in kw:
                    flags.append(f"{k}={kw[k]}")
            if "ForeignKey" in (c["type"] or ""):
                flags.append("FK")
            if flags:
                L.append(f'        attrs: "{esc(", ".join(flags))}"')
            if c["comment"]:
                L.append(f'        comment: "{esc(c["comment"])}"')
            vals = used.get(c["name"])
            if vals:
                items = ", ".join(f'"{esc(v)}"({n})' for v, n in vals.most_common(25))
                L.append(f'        실사용값: "{esc(items)}"')
                L.append(f'        사용파일수: {len(where[c["name"]])}')
                if c["name"] in NOISY:
                    L.append('        ⚠오탐주의: "흔한 이름이라 무관한 값이 섞였을 수 있음 — 사람 확인 필요"')
            L.append('        역할: ""      # ← 사람이 채움')
            L.append('        값의미: ""    # ← 사람이 채움: 각 값이 무엇을 뜻하나')
        L.append("")
    (OUT / "01-db-columns.yaml").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---- 설정 ----
    L = ["# 환경설정 (config.py Settings) — 기계 추출", "settings:"]
    for f in settings:
        L.append(f'  - name: "{esc(f["name"])}"')
        L.append(f'    type: "{esc(f["type"])}"')
        if f["default"] is not None:
            L.append(f'    default: "{esc(f["default"])}"')
        if f["comment"]:
            L.append(f'    comment: "{esc(f["comment"])}"')
        L.append(f"    line: {f['line']}")
        L.append('    역할: ""      # ← 사람이 채움')
    (OUT / "02-settings.yaml").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---- 상수 ----
    L = ["# 모듈 레벨 상수 (도메인 값 집합 포함) — 기계 추출", "constants:"]
    for c in constants:
        L.append(f'  - name: "{esc(c["name"])}"')
        L.append(f'    module: "{esc(c["module"])}:{c["line"]}"')
        L.append(f'    value: "{esc(c["value"])}"')
        if c["comment"]:
            L.append(f'    comment: "{esc(c["comment"])}"')
        L.append('    역할: ""      # ← 사람이 채움')
    (OUT / "03-constants.yaml").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---- 템플릿 변수 ----
    L = ["# 문자 템플릿 변수 ({{변수}}) — 기계 추출", "template_variables:"]
    for v in tvars:
        L.append(f'  - name: "{esc(v["name"])}"')
        for k in ("description", "example", "category"):
            if v.get(k):
                L.append(f'    {k}: "{esc(v[k])}"')
        L.append('    계산위치: ""   # ← 사람이 채움')
    (OUT / "04-template-vars.yaml").write_text("\n".join(L) + "\n", encoding="utf-8")

    ncols = sum(1 for m in models for c in m["cols"] if c["kind"] == "column")
    with_vals = sum(1 for m in models for c in m["cols"]
                    if c["kind"] == "column" and used.get(c["name"]))
    print(f"✅ 추출 완료 → {OUT.relative_to(REPO)}/")
    print(f"   모델 {len(models)} · 컬럼 {ncols} (실사용값 포착 {with_vals})")
    print(f"   설정 {len(settings)} · 상수 {len(constants)} · 템플릿변수 {len(tvars)}")

    if "--stats" in sys.argv:
        print("\n값 종류가 많은 컬럼 top 20:")
        for name, cnt in sorted(used.items(), key=lambda x: -len(x[1]))[:20]:
            vals = ", ".join(v for v, _ in cnt.most_common(8))
            print(f"  {len(cnt):3d}종  {name:28s} {vals}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
