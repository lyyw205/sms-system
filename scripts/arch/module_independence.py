#!/usr/bin/env python3
"""모듈 독립성(삭제 가능성) 측정 — 리팩토링 목표의 진행률 장치.

목표: "모듈 하나를 삭제해도 프로젝트 전체가 정상 동작한다"

측정 기준:
    모듈 M 을 지울 수 있다  ⟺  M 을 향하는 inbound import edge 중
                              bootstrap 발(發) 이 아닌 것이 0

  · bootstrap → M   은 배선이므로 삭제 시 그 줄만 지우면 됨 (깨지지 않음)
  · module   → M   은 삭제 시 그 모듈이 깨짐        ← R3 위반
  · core     → M   은 삭제 시 코어가 깨짐          ← R2 위반 (더 나쁨)

계층 판정은 check_layers.py 의 LEGACY_PLACEMENT / 경로 유도를 그대로 재사용한다.
따라서 파일을 실제로 옮기면 이 스크립트도 자동으로 새 배치를 반영한다.

사용:
    python scripts/arch/module_independence.py            # 요약표
    python scripts/arch/module_independence.py --list     # 붙잡는 선 전수
    python scripts/arch/module_independence.py --ci       # 삭제가능 수가 줄면 exit 1

exit code: 0 = 유지 또는 개선, 1 = 회귀, 2 = 사용 오류
"""
from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_layers as CL  # noqa: E402

BASELINE_DELETABLE = 2  # 2026-08-06 실측: party_ops · reporting


def collect_edges() -> list[tuple[str, str, str, str, str, bool]]:
    """(src_mod, src_layer, tgt_mod, tgt_layer, names, deferred)"""
    edges = []
    for path in CL.iter_files():
        mod = CL.module_name(path)
        if not mod:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        if path.name == "__init__.py" and not tree.body:
            continue
        src_layer = CL.placement(mod)
        if src_layer is None:
            continue

        deferred_nodes = set()
        for fn in (n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            for n in ast.walk(fn):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    deferred_nodes.add(id(n))

        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
                targets.append((node.module[4:], ",".join(a.name for a in node.names)))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("app."):
                        targets.append((a.name[4:], a.name))
            for tgt_mod, names in targets:
                tgt_layer = CL.placement(tgt_mod)
                if tgt_layer is None or tgt_layer == src_layer:
                    continue
                edges.append((mod, src_layer, tgt_mod, tgt_layer,
                              names, id(node) in deferred_nodes))
    return edges


def main() -> int:
    ap = argparse.ArgumentParser(description="모듈 독립성(삭제 가능성) 측정")
    ap.add_argument("--list", action="store_true", help="붙잡고 있는 선 전수 출력")
    ap.add_argument("--ci", action="store_true", help="삭제가능 모듈 수가 줄면 exit 1")
    args = ap.parse_args()

    edges = collect_edges()
    modules = sorted({l for l in (CL.placement(CL.module_name(p)) for p in CL.iter_files())
                      if l and l.startswith("module:")})

    rows = []
    for m in modules:
        inb_mod = [e for e in edges if e[3] == m and e[1].startswith("module:")]
        inb_core = [e for e in edges if e[3] == m and e[1].startswith("core:")]
        inb_boot = [e for e in edges if e[3] == m and e[1] == "bootstrap"]
        out_mod = [e for e in edges if e[1] == m and e[3].startswith("module:")]
        rows.append((m, len(inb_mod), len(inb_core), len(inb_boot),
                     len(out_mod), len(inb_mod) + len(inb_core)))

    deletable = sum(1 for r in rows if r[5] == 0)

    print("=" * 88)
    print("모듈 독립성 — 이 모듈을 통째로 지우면 몇 곳이 깨지는가")
    print("=" * 88)
    print(f"{'모듈':26s} {'←모듈':>6s} {'←코어':>6s} {'←부트':>6s} {'→모듈':>6s}   판정")
    print("-" * 88)
    for m, im, ic, ib, om, blocking in sorted(rows, key=lambda x: (x[5], x[0])):
        verdict = "✅ 삭제가능" if blocking == 0 else f"❌ {blocking}곳 깨짐"
        print(f"{m:26s} {im:6d} {ic:6d} {ib:6d} {om:6d}   {verdict}")

    total_inbound = sum(r[5] for r in rows)
    print("-" * 88)
    print(f"삭제 가능 모듈 : {deletable}/{len(rows)}   (기준선 {BASELINE_DELETABLE})")
    print(f"모듈 간 inbound: {total_inbound}   (목표 0)")

    if args.list:
        print()
        print("=" * 88)
        print("붙잡고 있는 선 — 삭제하려면 먼저 끊어야 할 것")
        print("=" * 88)
        for m, *_ , blocking in sorted(rows, key=lambda x: -x[5]):
            if not blocking:
                continue
            inb = [e for e in edges if e[3] == m and e[1] != "bootstrap"]
            print(f"\n### {m}  ({len(inb)}건)")
            agg = defaultdict(list)
            for e in inb:
                agg[(e[0], e[1])].append((e[4], e[5]))
            for (src, srcl), names in sorted(agg.items()):
                tag = "코어" if srcl.startswith("core") else "모듈"
                for nm, deferred in names:
                    d = " [지연]" if deferred else ""
                    print(f"  {tag} {src:34s} → {nm}{d}")

    if args.ci and deletable < BASELINE_DELETABLE:
        print(f"\n❌ 회귀: 삭제 가능 모듈이 {BASELINE_DELETABLE} → {deletable} 로 줄었습니다")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
