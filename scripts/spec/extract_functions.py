#!/usr/bin/env python3
"""backend/app 전 함수를 기계 추출 → 함수별 골격 YAML 생성.

목적: **누락 불가능성 확보.** 사람이 읽으며 의미를 채우기 전에, 함수·분기·예외·호출을
      AST 로 전부 뽑아 목록을 고정한다. 이후 의미 주석은 이 목록 위에만 얹는다.

추출 항목 (함수 1개당)
  - 시그니처 · 데코레이터 · async 여부 · 클래스 소속 · LOC
  - docstring (원문 유지)
  - 분기      : if / elif / ternary / bool 단축 — 조건식 원문
  - 예외      : raise (예외형 + 메시지) / try-except (잡는 예외 + 처리)
  - 조기반환  : guard clause (조건 + 반환값)
  - 호출      : app 내부 함수 호출
  - 데이터    : 모델 속성 읽기/쓰기
  - diag      : 발생시키는 diag 이벤트명
  - 부작용    : db.add / db.delete / db.commit / db.flush / setattr

출력: docs/plans/refactor/functions/<모듈경로>.yaml
사용: python scripts/spec/extract_functions.py [--stats]
"""
from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "backend" / "app"
OUT = REPO / "docs/plans/refactor/functions"

SIDE_EFFECTS = {"add", "delete", "commit", "flush", "rollback", "refresh",
                "add_all", "begin_nested", "merge", "expire"}

MODEL_NAMES = {
    "Reservation", "MessageTemplate", "ReservationSmsAssignment", "RoomBizItemLink",
    "Building", "RoomGroup", "Room", "RoomAssignment", "NaverBizItem", "TemplateSchedule",
    "ActivityLog", "PartyCheckin", "ReservationDailyInfo", "User", "ParticipantSnapshot",
    "Tenant", "UserTenantRole", "DailyHost", "PartyHost", "DailyReviewCount",
    "OnsiteFemaleInvite",
}
# 모델 인스턴스로 흔히 쓰이는 변수명 (속성 읽기/쓰기 추적용)
MODEL_VARS = {
    "res", "reservation", "db_reservation", "existing", "r", "rsv",
    "room", "db_room", "ra", "assignment", "chip", "sms", "template", "tpl",
    "schedule", "sch", "tenant", "user", "b", "building", "di", "daily",
    "snapshot", "log", "link", "biz", "biz_item", "group", "peer", "obj",
}


def esc(s: str) -> str:
    """YAML 안전 문자열."""
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\r", "").replace("\t", " ")
    return s


def short(s: str, n: int = 220) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


class FnVisitor(ast.NodeVisitor):
    """한 함수 본문을 훑어 분기/예외/호출/데이터를 수집. 중첩 함수는 건너뛴다."""

    def __init__(self, root):
        self.root = root
        self.branches: list[tuple[int, str]] = []
        self.ternaries: list[tuple[int, str]] = []
        self.raises: list[tuple[int, str]] = []
        self.excepts: list[tuple[int, str, str]] = []
        self.guards: list[tuple[int, str, str]] = []
        self.calls: list[tuple[int, str]] = []
        self.reads: set[str] = set()
        self.writes: set[str] = set()
        self.diags: list[tuple[int, str]] = []
        self.effects: list[tuple[int, str]] = []
        self.returns = 0
        self.loops = 0

    # 중첩 함수는 별도 항목으로 다루므로 진입하지 않음
    def visit_FunctionDef(self, node):
        if node is not self.root:
            return
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        cond = short(ast.unparse(node.test), 160)
        self.branches.append((node.lineno, cond))
        # guard clause: if <cond>: return/raise (본문 1~2줄)
        if len(node.body) <= 2 and isinstance(node.body[0], (ast.Return, ast.Raise, ast.Continue)):
            b = node.body[0]
            if isinstance(b, ast.Return):
                val = ast.unparse(b.value) if b.value else "None"
                self.guards.append((node.lineno, cond, f"return {short(val, 80)}"))
            elif isinstance(b, ast.Raise):
                self.guards.append((node.lineno, cond, short(ast.unparse(b), 100)))
            else:
                self.guards.append((node.lineno, cond, "continue"))
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.ternaries.append((node.lineno, short(ast.unparse(node), 140)))
        self.generic_visit(node)

    def visit_Raise(self, node):
        self.raises.append((node.lineno, short(ast.unparse(node), 180)))
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        typ = ast.unparse(node.type) if node.type else "Exception(bare)"
        first = ""
        if node.body:
            b = node.body[0]
            if isinstance(b, ast.Pass):
                first = "pass (완전 억제)"
            else:
                first = short(ast.unparse(b), 110)
        self.excepts.append((node.lineno, short(typ, 60), first))
        self.generic_visit(node)

    def visit_Return(self, node):
        self.returns += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.loops += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.loops += 1
        self.generic_visit(node)

    def visit_Call(self, node):
        f = node.func
        name = None
        if isinstance(f, ast.Name):
            name = f.id
        elif isinstance(f, ast.Attribute):
            base = f.value
            if isinstance(base, ast.Name):
                name = f"{base.id}.{f.attr}"
                # 부작용
                if base.id in ("db", "session", "sess") and f.attr in SIDE_EFFECTS:
                    self.effects.append((node.lineno, f"db.{f.attr}"))
            else:
                name = f".{f.attr}"
        if name:
            self.calls.append((node.lineno, name))
            if name == "diag" and node.args and isinstance(node.args[0], ast.Constant):
                self.diags.append((node.lineno, str(node.args[0].value)))
            if name == "setattr" and len(node.args) >= 2:
                tgt = ast.unparse(node.args[1]) if not isinstance(node.args[1], ast.Constant) else repr(node.args[1].value)
                self.effects.append((node.lineno, f"setattr({short(tgt,40)})"))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        base = node.value
        if isinstance(base, ast.Name):
            if base.id in MODEL_NAMES:
                self.reads.add(f"{base.id}.{node.attr}")
            elif base.id in MODEL_VARS:
                self.reads.add(f"<{base.id}>.{node.attr}")
        self.generic_visit(node)

    def visit_Assign(self, node):
        for t in node.targets:
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
                b = t.value.id
                if b in MODEL_VARS or b in MODEL_NAMES:
                    tag = f"{b}.{t.attr}" if b in MODEL_NAMES else f"<{b}>.{t.attr}"
                    self.writes.add(tag)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        t = node.target
        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
            b = t.value.id
            if b in MODEL_VARS or b in MODEL_NAMES:
                tag = f"{b}.{t.attr}" if b in MODEL_NAMES else f"<{b}>.{t.attr}"
                self.writes.add(tag)
        self.generic_visit(node)


def sig_of(node) -> str:
    a = node.args
    parts = []
    defaults = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
    for arg, dflt in zip(a.args, defaults):
        s = arg.arg
        if arg.annotation is not None:
            s += f": {short(ast.unparse(arg.annotation), 40)}"
        if dflt is not None:
            s += f" = {short(ast.unparse(dflt), 30)}"
        parts.append(s)
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    if a.kwonlyargs:
        if not a.vararg:
            parts.append("*")
        kwd = list(a.kw_defaults)
        for arg, dflt in zip(a.kwonlyargs, kwd):
            s = arg.arg
            if arg.annotation is not None:
                s += f": {short(ast.unparse(arg.annotation), 40)}"
            if dflt is not None:
                s += f" = {short(ast.unparse(dflt), 30)}"
            parts.append(s)
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    ret = f" -> {short(ast.unparse(node.returns), 50)}" if node.returns else ""
    return f"({', '.join(parts)}){ret}"


def collect(path: Path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    rel = path.relative_to(APP).as_posix()
    mod_doc = ast.get_docstring(tree)

    items = []

    def walk(node, cls: str | None, depth: int):
        for child in node.body:
            if isinstance(child, ast.ClassDef):
                walk(child, child.name, depth)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                items.append((child, cls, depth))
                # 중첩 함수도 수집 (depth+1)
                for sub in child.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        items.append((sub, cls, depth + 1))

    walk(tree, None, 0)

    out = []
    for node, cls, depth in items:
        v = FnVisitor(node)
        v.visit(node)
        internal_calls = [(ln, c) for ln, c in v.calls
                          if not c.startswith(".") and "." in c or c[:1].isupper() or c.islower()]
        out.append({
            "node": node, "cls": cls, "depth": depth, "v": v,
        })
    return rel, mod_doc, src, out


def emit(rel: str, mod_doc, src: str, fns) -> str:
    L = []
    A = L.append
    A(f'module: "{esc(rel)}"')
    A(f"loc: {len(src.splitlines())}")
    A(f"functions: {len(fns)}")
    if mod_doc:
        A(f'module_doc: "{esc(short(mod_doc, 900))}"')
    A("# ── 아래는 AST 기계 추출. `역할:` `주의:` 필드는 사람이 채운다 ──")
    A("fns:")
    for item in fns:
        node, cls, depth, v = item["node"], item["cls"], item["depth"], item["v"]
        doc = ast.get_docstring(node)
        name = f"{cls}.{node.name}" if cls else node.name
        if depth:
            name = "  ↳" + name
        A(f'  - name: "{esc(name)}"')
        A(f'    sig: "{esc(short(sig_of(node), 300))}"')
        A(f"    line: {node.lineno}")
        A(f"    loc: {node.end_lineno - node.lineno + 1}")
        if isinstance(node, ast.AsyncFunctionDef):
            A("    is_async: true")
        if node.decorator_list:
            decs = [short(ast.unparse(d), 80) for d in node.decorator_list]
            A(f'    decorators: [{", ".join(chr(34)+esc(d)+chr(34) for d in decs)}]')
        if doc:
            A(f'    doc: "{esc(short(doc, 700))}"')
        A('    역할: ""          # ← 사람이 채움: 이 함수가 무엇을 책임지는가')
        A('    주의: ""          # ← 사람이 채움: 옮길 때 깨지기 쉬운 것')
        if v.guards:
            A("    guards:        # 조기 반환/차단")
            for ln, c, act in v.guards:
                A(f'      - "L{ln}: {esc(short(c,140))} → {esc(act)}"')
        if v.branches:
            A(f"    branches: # {len(v.branches)}")
            for ln, c in v.branches:
                A(f'      - "L{ln}: {esc(c)}"')
        if v.ternaries:
            A("    ternaries:")
            for ln, c in v.ternaries:
                A(f'      - "L{ln}: {esc(c)}"')
        if v.raises:
            A("    raises:")
            for ln, r in v.raises:
                A(f'      - "L{ln}: {esc(r)}"')
        if v.excepts:
            A("    excepts:")
            for ln, t, b in v.excepts:
                A(f'      - "L{ln}: except {esc(t)} → {esc(b)}"')
        if v.diags:
            A("    diag:")
            for ln, e in v.diags:
                A(f'      - "L{ln}: {esc(e)}"')
        if v.effects:
            seen = []
            for ln, e in v.effects:
                if e not in [x[1] for x in seen]:
                    seen.append((ln, e))
            A(f'    effects: [{", ".join(chr(34)+esc(e)+chr(34) for _, e in seen)}]')
        if v.writes:
            A(f'    writes: [{", ".join(chr(34)+esc(w)+chr(34) for w in sorted(v.writes))}]')
        if v.reads:
            rd = sorted(v.reads)
            if len(rd) > 40:
                rd = rd[:40] + [f"…외 {len(v.reads)-40}"]
            A(f'    reads: [{", ".join(chr(34)+esc(w)+chr(34) for w in rd)}]')
        # 내부 호출만 (표준/빌트인 제외)
        calls = []
        for ln, c in v.calls:
            if c in ("diag", "print", "len", "str", "int", "list", "dict", "set", "bool",
                     "sorted", "isinstance", "getattr", "setattr", "hasattr", "range",
                     "enumerate", "zip", "max", "min", "sum", "any", "all", "tuple", "float"):
                continue
            if c not in calls:
                calls.append(c)
        if calls:
            if len(calls) > 45:
                calls = calls[:45] + [f"…외 {len(v.calls)-45}"]
            A(f'    calls: [{", ".join(chr(34)+esc(c)+chr(34) for c in calls)}]')
        stats = f"returns={v.returns} loops={v.loops}"
        A(f'    stats: "{stats}"')
    return "\n".join(L) + "\n"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tot = Counter()
    files = []
    for p in sorted(APP.rglob("*.py")):
        if "_future" in p.parts or "__pycache__" in p.parts:
            continue
        rel, mod_doc, src, fns = collect(p)
        if not fns:
            continue
        dest = OUT / rel.replace("/", "__").replace(".py", ".yaml")
        dest.write_text(emit(rel, mod_doc, src, fns), encoding="utf-8")
        tot["files"] += 1
        tot["fns"] += len(fns)
        for it in fns:
            v = it["v"]
            tot["branches"] += len(v.branches)
            tot["guards"] += len(v.guards)
            tot["raises"] += len(v.raises)
            tot["excepts"] += len(v.excepts)
            tot["diag"] += len(v.diags)
        files.append((rel, len(fns), sum(len(it["v"].branches) for it in fns)))

    print(f"✅ 추출 완료 → {OUT.relative_to(REPO)}/")
    print(f"   파일 {tot['files']} · 함수 {tot['fns']}")
    print(f"   분기 {tot['branches']} · 가드 {tot['guards']} · raise {tot['raises']} "
          f"· except {tot['excepts']} · diag {tot['diag']}")
    if "--stats" in sys.argv:
        print("\n분기 상위 20 파일:")
        for rel, nf, nb in sorted(files, key=lambda x: -x[2])[:20]:
            print(f"  {nb:5d} 분기 / {nf:3d} 함수  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
