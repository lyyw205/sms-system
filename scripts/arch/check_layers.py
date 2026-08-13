#!/usr/bin/env python3
"""아키텍처 계층 규칙 검사기 — 코어/모듈 2층 리팩토링의 진행률 측정 장치.

  docs/plans/architecture-refactor-01-target.md §1 의 의존 규칙(R1~R6)을 강제한다.

규칙:
  R1  모듈 → 코어             허용
  R2  코어 → 모듈             금지
  R3  모듈 → 모듈             금지
  R4  bootstrap → 전부        허용 (composition root)
  R5  함수 내부 지연 import    금지 (R1~R3 위반의 증상)
  R6  diag() 이벤트 문자열     동결 (파일이 이동해도 불변)

이동 전/중/후 모두 동작한다:
  - `app.core.X` / `app.modules.X` / `app.bootstrap` 은 경로에서 계층을 유도
  - 아직 안 옮긴 파일은 LEGACY_PLACEMENT 로 목표 계층을 조회

사용:
    python scripts/arch/check_layers.py              # 요약 + baseline 대비
    python scripts/arch/check_layers.py --list       # 위반 전수 출력
    python scripts/arch/check_layers.py --write-baseline
    python scripts/arch/check_layers.py --write-diag-snapshot
    python scripts/arch/check_layers.py --ci         # 신규 위반 있으면 exit 1

exit code: 0 = baseline 이내, 1 = 신규 위반(회귀), 2 = 사용 오류
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "backend" / "app"
HERE = Path(__file__).resolve().parent
BASELINE = HERE / "baseline.txt"
DIAG_SNAPSHOT = HERE / "diag_events.json"

# ---------------------------------------------------------------------------
# 계층 배치 — 아직 이동하지 않은 파일의 목표 계층
# 파일을 옮기면 이 표에서 해당 줄을 지운다 (경로에서 자동 유도되므로).
# ---------------------------------------------------------------------------
LEGACY_PLACEMENT: dict[str, str] = {
    # ---- bootstrap (composition root — 모든 모듈을 알아도 되는 유일한 곳) ----
    "main":                  "bootstrap",
    "db.seed":               "bootstrap",
    "scheduler.jobs":        "bootstrap",   # 패턴 C — 모듈이 아니라 배선 파일
    "scheduler":             "bootstrap",   # __init__ 가 jobs 를 re-export

    # ---- 패키지 __init__ re-export (이동 시 소멸) ----
    "real":                  "module:naver",     # ⚠ sms/reservation 두 모듈을 함께 re-export
    "templates":             "module:sms_send",

    # ---- core ----
    "config":                            "core:config",
    "rate_limit":                        "core:config",
    "db.database":                       "core:db",
    "factory":                           "core:providers",   # ⚠ Q9 — 죽은 추상화 결정 대기
    "providers.base":                    "core:providers",
    "db.models":                         "core:models",
    "db.tenant_context":                 "core:tenant",
    "api.deps":                          "core:tenant",
    "auth.utils":                        "core:tenant",
    "auth.schemas":                      "core:tenant",
    "auth.dependencies":                 "core:tenant",
    "services.reservation_mutator":      "core:reservation",
    "services.stay_logic":               "core:calendar",
    "services.schedule_utils":           "core:calendar",
    "services.chip_store":               "core:chip",
    "services.chip_reconciler":          "core:chip",
    "services.section_registry":         "core:vocabulary",
    "services.party_type":               "core:vocabulary",
    "services.room_grade":               "core:vocabulary",
    "services.reservation_lifecycle":    "core:lifecycle",
    "services.reconcile":                "core:lifecycle",
    "diag_logger":                       "core:observability",
    "services.activity_logger":          "core:observability",
    "services.event_bus":                "core:observability",
    # 승격 예정 (아직 미분리 — 분리 시 이 줄들이 실현된다)
    "services.room_lookup":              "core:lookup",         # 패턴 E / F9

    # ---- modules ----
    "services.room_assignment":              "module:room_assign",
    "services.room_auto_assign":             "module:room_assign",
    "services.room_assignment_invariants":   "module:room_assign",
    "services.dorm_gender":                  "module:room_assign",
    "services.password_display":             "module:room_assign",
    "api.rooms":                             "module:room_assign",
    "api.reservations_room":                 "module:room_assign",
    "api.buildings":                         "module:room_assign",

    "services.sms_sender":       "module:sms_send",
    "real.sms":                  "module:sms_send",
    "templates.renderer":        "module:sms_send",
    "templates.variables":       "module:sms_send",
    "api.reservations_sms":      "module:sms_send",
    "api.templates":             "module:sms_send",   # 패턴 E — 템플릿 CRUD 는 M2 소속

    "scheduler.template_scheduler":  "module:scheduling",
    "scheduler.schedule_manager":    "module:scheduling",
    "services.filters":              "module:scheduling",   # ⚠ 분할 대상 (§2)
    "api.template_schedules":        "module:scheduling",
    "api.scheduler":                 "module:scheduling",

    "services.custom_schedule_registry":  "module:custom_sends",  # ⚠ 분할 대상 (§2)
    "services.surcharge":                 "module:custom_sends",
    "services.party3_mms":                "module:custom_sends",
    "services.room_upgrade_common":       "module:custom_sends",
    "services.room_upgrade_promise":      "module:custom_sends",
    "services.room_upgrade_review":       "module:custom_sends",

    "services.naver_sync":     "module:naver",
    "real.reservation":        "module:naver",

    "api.party_checkin":          "module:party_ops",
    "api.party_hosts":            "module:party_ops",
    "api.daily_host":             "module:party_ops",
    "api.daily_review":           "module:party_ops",
    "api.onsite_female_invite":   "module:party_ops",
    "api.cleancrew":              "module:party_ops",

    "services.consecutive_stay":    "module:stay_group",
    "services.split_group_guard":   "module:stay_group",
    "api.reservations_stay":        "module:stay_group",

    "api.sales_report":     "module:reporting",
    "api.dashboard":        "module:reporting",
    "api.activity_logs":    "module:reporting",

    "api.event_sms":              "module:event_sms",
    "services.event_sms_hook":    "module:event_sms",

    "api.reservations":          "module:reservation_api",
    "api.reservations_shared":   "module:reservation_api",
    "api.shared_schemas":        "module:reservation_api",
    "api.auth":                  "module:reservation_api",
    "api.settings":              "module:reservation_api",
    "api.tenants":               "module:reservation_api",
    "api.events":                "module:reservation_api",
}


def placement(mod: str) -> str | None:
    """`app.` 을 뗀 모듈명 → 계층 id. 목표 경로 우선, 없으면 legacy 표."""
    parts = mod.split(".")
    if parts[0] == "bootstrap":
        return "bootstrap"
    if parts[0] == "core":
        return f"core:{parts[1]}" if len(parts) > 1 else "core:?"
    if parts[0] == "modules":
        return f"module:{parts[1]}" if len(parts) > 1 else "module:?"
    return LEGACY_PLACEMENT.get(mod)


def kind(layer: str) -> str:
    return layer.split(":")[0]


# ---------------------------------------------------------------------------
# 수집
# ---------------------------------------------------------------------------
class Violation:
    __slots__ = ("src_mod", "src_layer", "lineno", "tgt_mod", "tgt_layer", "names", "deferred", "rule")

    def __init__(self, src_mod, src_layer, lineno, tgt_mod, tgt_layer, names, deferred, rule):
        self.src_mod, self.src_layer, self.lineno = src_mod, src_layer, lineno
        self.tgt_mod, self.tgt_layer, self.names = tgt_mod, tgt_layer, names
        self.deferred, self.rule = deferred, rule

    def key(self) -> str:
        """baseline 대조용 안정 키 — 라인번호 제외(코드가 움직여도 유지)."""
        return f"{self.rule} {self.src_mod} -> {self.tgt_mod} :: {self.names}"

    def __str__(self) -> str:
        d = " [지연]" if self.deferred else ""
        return (f"{self.rule} {self.src_layer:22s} -> {self.tgt_layer:22s} "
                f"{self.src_mod}:{self.lineno}{d}  {self.tgt_mod} :: {self.names}")


def iter_files():
    for dirpath, dirnames, filenames in os.walk(APP):
        dirnames[:] = [d for d in dirnames if d not in {"__pycache__", "_future"}]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def module_name(path: Path) -> str:
    rel = path.relative_to(APP).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join(parts)


def collect():
    violations: list[Violation] = []
    deferred_total = 0
    deferred_by_file: Counter = Counter()
    diag_events: dict[str, list[str]] = defaultdict(list)
    unmapped: list[str] = []

    for path in iter_files():
        mod = module_name(path)
        if not mod:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            print(f"⚠ 파싱 실패 {path}: {e}", file=sys.stderr)
            continue

        # 빈 패키지 __init__.py 는 계층 대상이 아님
        if path.name == "__init__.py" and not tree.body:
            continue

        src_layer = placement(mod)
        if src_layer is None:
            unmapped.append(mod)
            continue

        # 함수 내부에 있는 import 노드 식별 (R5)
        deferred_nodes: set[int] = set()
        for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            for n in ast.walk(fn):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    deferred_nodes.add(id(n))

        for node in ast.walk(tree):
            # --- diag 이벤트 문자열 수집 (R6) ---
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "diag" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                diag_events[node.args[0].value].append(mod)

            # --- import 규칙 ---
            targets: list[tuple[str, str]] = []
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
                targets.append((node.module[4:], ",".join(a.name for a in node.names)))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("app."):
                        targets.append((a.name[4:], a.name))
            if not targets:
                continue

            is_deferred = id(node) in deferred_nodes
            if is_deferred:
                deferred_total += 1
                deferred_by_file[mod] += 1

            for tgt_mod, names in targets:
                tgt_layer = placement(tgt_mod)
                if tgt_layer is None or tgt_layer == src_layer:
                    continue
                sk, tk = kind(src_layer), kind(tgt_layer)
                rule = None
                if sk == "bootstrap":
                    rule = None                       # R4 — 전부 허용
                elif sk == "core" and tk == "module":
                    rule = "R2"
                elif sk == "module" and tk == "module":
                    rule = "R3"
                elif sk == "module" and tk == "bootstrap":
                    rule = "R3"                       # 모듈이 배선 파일에 의존 = 역방향
                elif sk == "core" and tk == "bootstrap":
                    rule = "R2"
                if rule:
                    violations.append(Violation(mod, src_layer, node.lineno, tgt_mod,
                                                tgt_layer, names, is_deferred, rule))

    return violations, deferred_total, deferred_by_file, diag_events, unmapped


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="아키텍처 계층 규칙 검사기")
    ap.add_argument("--list", action="store_true", help="위반 전수 출력")
    ap.add_argument("--write-baseline", action="store_true", help="현재 위반을 baseline 으로 기록")
    ap.add_argument("--write-diag-snapshot", action="store_true", help="현재 diag 이벤트를 스냅샷으로 기록")
    ap.add_argument("--ci", action="store_true", help="신규 위반/diag 변경 시 exit 1")
    args = ap.parse_args()

    violations, deferred_total, deferred_by_file, diag_events, unmapped = collect()

    if unmapped:
        print("⚠ 계층 미배정 모듈 (LEGACY_PLACEMENT 에 추가 필요):")
        for m in sorted(unmapped):
            print(f"   {m}")
        print()

    if args.write_baseline:
        keys = sorted({v.key() for v in violations})
        BASELINE.write_text("\n".join(keys) + "\n", encoding="utf-8")
        print(f"✅ baseline 기록: {len(keys)} 항목 → {BASELINE.relative_to(REPO)}")
        return 0

    if args.write_diag_snapshot:
        snap = {k: sorted(set(v)) for k, v in sorted(diag_events.items())}
        DIAG_SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ diag 스냅샷 기록: {len(snap)} 이벤트 → {DIAG_SNAPSHOT.relative_to(REPO)}")
        return 0

    # ---- 요약 ----
    by_rule = Counter(v.rule for v in violations)
    by_pair = Counter((v.src_layer, v.tgt_layer) for v in violations)

    print("=" * 72)
    print("아키텍처 계층 검사 — 코어/모듈 2층")
    print("=" * 72)
    print(f"위반 총계         : {len(violations)}")
    print(f"  R2 코어 → 모듈  : {by_rule.get('R2', 0)}")
    print(f"  R3 모듈 → 모듈  : {by_rule.get('R3', 0)}")
    print(f"R5 지연 import    : {deferred_total}  ({len(deferred_by_file)} 파일)")
    print(f"R6 diag 이벤트    : {len(diag_events)} 종")
    print()

    print("--- 계층쌍별 ---")
    for (s, t), c in by_pair.most_common():
        print(f"{c:4d}  {s:24s} -> {t}")
    print()

    print("--- 지연 import 상위 ---")
    for m, c in deferred_by_file.most_common(10):
        print(f"{c:4d}  {m}")
    print()

    if args.list:
        print("--- 위반 전수 ---")
        for v in sorted(violations, key=lambda v: (v.src_layer, v.tgt_layer, v.src_mod, v.lineno)):
            print(f"  {v}")
        print()

    # ---- baseline 대조 ----
    exit_code = 0
    if BASELINE.exists():
        base = {ln.strip() for ln in BASELINE.read_text(encoding="utf-8").splitlines() if ln.strip()}
        cur = {v.key() for v in violations}
        new, fixed = cur - base, base - cur
        print(f"--- baseline 대조 (기준 {len(base)}건) ---")
        print(f"해소   : {len(fixed)}")
        print(f"신규   : {len(new)}")
        for k in sorted(new):
            print(f"  🔴 {k}")
        if fixed:
            for k in sorted(fixed):
                print(f"  ✅ {k}")
        if new and args.ci:
            exit_code = 1
    else:
        print("ℹ baseline 없음 — `--write-baseline` 으로 기준선을 만드세요.")

    # ---- diag 동결 대조 (R6) ----
    if DIAG_SNAPSHOT.exists():
        snap = json.loads(DIAG_SNAPSHOT.read_text(encoding="utf-8"))
        removed = sorted(set(snap) - set(diag_events))
        added = sorted(set(diag_events) - set(snap))
        print()
        print(f"--- R6 diag 동결 (기준 {len(snap)} 이벤트) ---")
        print(f"사라진 이벤트 : {len(removed)}")
        for e in removed:
            print(f"  🔴 {e}   (was in {', '.join(snap[e])})")
        print(f"새 이벤트     : {len(added)}")
        for e in added:
            print(f"  🟡 {e}   (in {', '.join(sorted(set(diag_events[e])))})")
        if removed and args.ci:
            exit_code = 1
    else:
        print("\nℹ diag 스냅샷 없음 — `--write-diag-snapshot` 으로 기준선을 만드세요.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
