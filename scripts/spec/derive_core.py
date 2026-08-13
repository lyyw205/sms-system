#!/usr/bin/env python3
"""코어 도출 (S5) — 전수조사 결과를 집계해 "무엇이 코어인가" 를 계산으로 뽑는다.

원칙: 코어를 **가정하지 않는다**. 아래 지표로만 판정한다.

  확산도(spread)  그 심볼을 쓰는 **도메인 수**. 여러 도메인이 쓰면 어느 한 도메인의
                  소유가 아니다 → 코어.
  등급            S1 에서 사람이 매긴 D(업무규칙)/G(보호장치)/L/N/I.
                  I 는 확산돼도 유틸일 뿐 도메인 코어가 아니다.
  보호밀도        그 데이터를 다루는 G 등급 함수 수. 높으면 여러 곳이 각자 지키고
                  있다는 뜻 → **강제 관문 후보**.

입력
  docs/plans/refactor/functions/*.yaml   기계 추출 골격 (calls/reads/writes)
  docs/plans/refactor/semantics/*.yaml   사람이 쓴 역할/등급/핵심/주의
  backend/app/**.py                      실제 import 관계 (정확도용)

출력
  docs/plans/refactor/코어도출/*.md
"""
from __future__ import annotations

import ast
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML 필요:  pip install pyyaml")

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "backend" / "app"
FUNCS = REPO / "docs/plans/refactor/functions"
SEM = REPO / "docs/plans/refactor/semantics"
OUT = REPO / "docs/plans/refactor/코어도출"

# ── 모듈 → 도메인 (S1 에서 정한 13 도메인) ────────────────────────────
DOMAIN = {
    "RES":     ["api/reservations.py", "api/reservations_shared.py", "api/shared_schemas.py"],
    "ROOM":    ["api/rooms.py", "api/reservations_room.py", "api/buildings.py",
                "services/room_assignment.py", "services/room_auto_assign.py",
                "services/room_assignment_invariants.py", "services/room_lookup.py",
                "services/dorm_gender.py", "services/password_display.py",
                "services/room_grade.py"],
    "STAY":    ["api/reservations_stay.py", "services/consecutive_stay.py",
                "services/split_group_guard.py", "services/stay_logic.py"],
    "NAVER":   ["services/naver_sync.py", "real/reservation.py"],
    "CHIP":    ["services/chip_store.py", "services/chip_reconciler.py",
                "services/reconcile.py", "services/reservation_lifecycle.py",
                "services/reservation_mutator.py"],
    "SCHED":   ["scheduler/template_scheduler.py", "scheduler/schedule_manager.py",
                "api/template_schedules.py", "services/filters.py",
                "services/schedule_utils.py", "api/scheduler.py",
                "services/custom_schedule_registry.py"],
    "SMS":     ["services/sms_sender.py", "real/sms.py", "templates/renderer.py",
                "templates/variables.py", "api/reservations_sms.py", "api/templates.py"],
    "CUSTOM":  ["services/surcharge.py", "services/party3_mms.py",
                "services/room_upgrade_common.py", "services/room_upgrade_promise.py",
                "services/room_upgrade_review.py"],
    "PARTY":   ["api/party_checkin.py", "api/party_hosts.py", "api/daily_host.py",
                "api/daily_review.py", "api/onsite_female_invite.py", "api/cleancrew.py",
                "services/party_type.py", "services/section_registry.py"],
    "REPORT":  ["api/dashboard.py", "api/sales_report.py", "api/activity_logs.py"],
    "EVENT":   ["api/event_sms.py", "services/event_sms_hook.py"],
    "AUTH":    ["api/auth.py", "api/settings.py", "api/tenants.py", "api/deps.py",
                "auth/utils.py", "auth/dependencies.py", "auth/schemas.py",
                "db/tenant_context.py"],
    "INFRA":   ["main.py", "config.py", "factory.py", "rate_limit.py", "diag_logger.py",
                "db/database.py", "db/models.py", "db/seed.py", "api/events.py",
                "scheduler/jobs.py", "providers/base.py",
                "services/activity_logger.py", "services/event_bus.py"],
}
MOD2DOM = {m: d for d, ms in DOMAIN.items() for m in ms}

GRADE_LABEL = {"D": "업무규칙", "G": "보호장치", "L": "옛데이터", "N": "존재확인", "I": "기술처리"}


def load_semantics():
    """(module, fn) → {역할, 등급, 핵심, 주의, 순서}"""
    out = {}
    for p in sorted(SEM.glob("*.yaml")):
        for m in (yaml.safe_load(p.read_text(encoding="utf-8")) or []):
            if not m or "module" not in m:
                continue
            for fn, meta in (m.get("fns") or {}).items():
                out[(m["module"], fn)] = meta or {}
    return out


def load_skeletons():
    """module → [fn dict]"""
    out = {}
    for p in sorted(FUNCS.glob("*.yaml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        out[d["module"]] = d.get("fns") or []
    return out


def scan_imports():
    """(owner_module, symbol) → {importer_module: count}"""
    usage = defaultdict(lambda: defaultdict(int))
    for p in sorted(APP.rglob("*.py")):
        if "_future" in p.parts or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(APP).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app."):
                owner = n.module[4:].replace(".", "/") + ".py"
                for a in n.names:
                    usage[(owner, a.name)][rel] += 1
    return usage


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sem = load_semantics()
    skel = load_skeletons()
    usage = scan_imports()

    # ── 심볼별 집계 ──────────────────────────────────────────────
    rows = []
    for (owner, sym), importers in usage.items():
        owner_dom = MOD2DOM.get(owner)
        doms = {MOD2DOM.get(m) for m in importers if MOD2DOM.get(m)}
        doms.discard(None)
        outside = {d for d in doms if d != owner_dom}
        meta = sem.get((owner, sym)) or {}
        # 클래스 메서드 표기 보정 (Foo.bar)
        if not meta:
            for (m2, f2), v in sem.items():
                if m2 == owner and f2.endswith("." + sym):
                    meta = v
                    break
        rows.append({
            "owner": owner, "owner_dom": owner_dom, "sym": sym,
            "importers": len(importers), "domains": sorted(doms),
            "spread": len(outside), "grade": meta.get("등급", "?"),
            "role": meta.get("역할", ""), "core": bool(meta.get("핵심")),
            "caution": meta.get("주의", ""),
        })

    # ── 데이터(모델) 사용 집계 ────────────────────────────────────
    data_dom = defaultdict(set)
    data_guard = Counter()
    data_use = Counter()
    for mod, fns in skel.items():
        dom = MOD2DOM.get(mod)
        for f in fns:
            key = f["name"].replace("↳", "").strip()
            meta = sem.get((mod, key)) or {}
            grade = meta.get("등급", "?")
            touched = set()
            for w in (f.get("writes") or []) + (f.get("reads") or []):
                m = re.match(r"^([A-Z][A-Za-z]*)\.(\w+)$", w)
                if m:
                    touched.add(f"{m.group(1)}.{m.group(2)}")
            for t in touched:
                data_use[t] += 1
                if dom:
                    data_dom[t].add(dom)
                if grade == "G":
                    data_guard[t] += 1

    # ══════════════════════════════════════════════════════════
    L = []
    A = L.append
    A("# 코어 도출 — 계산 결과")
    A("")
    A("> `scripts/spec/derive_core.py` 자동 생성. **직접 고치지 마세요.**")
    A(">")
    A("> 코어를 가정하지 않고, **여러 도메인이 쓰는가**로만 판정합니다.")
    A("")
    A("## 판정 기준")
    A("")
    A("| 확산도 | 뜻 | 판정 |")
    A("|-------:|-----|------|")
    A("| 3+ | 3개 이상의 다른 도메인이 쓴다 | ⭐ **코어** |")
    A("| 2 | 2개 다른 도메인이 쓴다 | 🟡 코어 후보 |")
    A("| 1 | 1개 다른 도메인만 쓴다 | · 공유 (관찰) |")
    A("| 0 | 자기 도메인 안에서만 쓴다 | 도메인 소유 |")
    A("")
    A("등급 `I`(기술처리)는 확산돼도 **유틸**이지 도메인 코어가 아닙니다. 따로 표시합니다.")
    A("")

    core = [r for r in rows if r["spread"] >= 3]
    cand = [r for r in rows if r["spread"] == 2]
    shared = [r for r in rows if r["spread"] == 1]

    def table(rs, title, note=""):
        A(f"## {title}")
        A("")
        if note:
            A(note)
            A("")
        if not rs:
            A("(없음)")
            A("")
            return
        A("| 심볼 | 현재 위치 | 쓰는 도메인 | 확산 | 등급 | 역할 |")
        A("|------|-----------|-------------|-----:|------|------|")
        for r in sorted(rs, key=lambda x: (-x["spread"], -x["importers"], x["sym"])):
            g = r["grade"]
            gl = f"{g} {GRADE_LABEL.get(g, '')}" if g != "?" else "—"
            star = "⭐ " if r["core"] else ""
            role = (r["role"] or "")[:60]
            A(f"| {star}`{r['sym']}` | `{r['owner']}` | {', '.join(r['domains'])} "
              f"| {r['spread']} | {gl} | {role} |")
        A("")

    dom_core = [r for r in core if r["grade"] in ("D", "G")]
    util_core = [r for r in core if r["grade"] not in ("D", "G")]

    table(dom_core, "1. ⭐ 코어 확정 — 업무규칙·보호장치이면서 3개 이상 도메인이 씀")
    table(util_core, "2. 공용 유틸 — 확산은 넓지만 기술처리",
          "코어 층에 두되, 도메인 판단이 아니라 **인프라**로 분류합니다.")
    table([r for r in cand if r["grade"] in ("D", "G")], "3. 🟡 코어 후보 — 2개 도메인")
    table([r for r in shared if r["grade"] in ("D", "G")], "4. 공유 — 1개 도메인만 (관찰)")

    # ── 데이터 ────────────────────────────────────────────────
    A("## 5. 데이터 — 어느 데이터가 여러 도메인에 걸쳐 있나")
    A("")
    A("| 데이터 | 쓰는 도메인 | 확산 | 다루는 함수 | 보호장치 함수 | 판정 |")
    A("|--------|-------------|-----:|------------:|--------------:|------|")
    for t, doms in sorted(data_dom.items(), key=lambda x: (-len(x[1]), -data_use[x[0]])):
        if len(doms) < 2 and data_guard.get(t, 0) < 2:
            continue
        v = []
        if len(doms) >= 3:
            v.append("⭐ 코어")
        elif len(doms) == 2:
            v.append("🟡 공유")
        if data_guard.get(t, 0) >= 2:
            v.append("🛡 **관문후보**")
        A(f"| `{t}` | {', '.join(sorted(doms))} | {len(doms)} | {data_use[t]} "
          f"| {data_guard.get(t, 0)} | {' '.join(v) or '·'} |")
    A("")
    A("> **보호장치 함수**가 2 이상 = 여러 곳이 그 데이터를 **각자** 지키고 있다는 뜻.")
    A("> 쓰기를 한 관문으로 강제하면 흩어진 보호 코드가 한 곳으로 모입니다.")
    A("")

    # ── 도메인별 요약 ──────────────────────────────────────────
    A("## 6. 도메인별 — 내보내는 심볼 수")
    A("")
    A("| 도메인 | 코어로 빠질 심볼 | 도메인에 남을 심볼 |")
    A("|--------|------------------:|-------------------:|")
    by_dom = defaultdict(lambda: [0, 0])
    for r in rows:
        if not r["owner_dom"]:
            continue
        if r["spread"] >= 2 and r["grade"] in ("D", "G"):
            by_dom[r["owner_dom"]][0] += 1
        else:
            by_dom[r["owner_dom"]][1] += 1
    for d in sorted(by_dom, key=lambda x: -by_dom[x][0]):
        a, b = by_dom[d]
        A(f"| {d} | {a} | {b} |")
    A("")

    # ── 순서 의존 ──────────────────────────────────────────────
    orders = [(m, f, v) for (m, f), v in sem.items() if v.get("순서")]
    A("## 7. ⚠️ 순서 의존 — 재조립 시 절대 보존")
    A("")
    for m, f, v in sorted(orders):
        A(f"- **`{f}`** <sub>{m}</sub>")
        A(f"  - {v['순서']}")
    A("")

    (OUT / "요약.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"✅ {(OUT / '요약.md').relative_to(REPO)}")
    print(f"   심볼 {len(rows)} · 코어확정 {len(dom_core)} · 공용유틸 {len(util_core)} "
          f"· 후보 {len([r for r in cand if r['grade'] in ('D','G')])}")
    print(f"   데이터 {len(data_dom)} · 순서의존 {len(orders)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
