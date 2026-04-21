#!/usr/bin/env python3
"""
Incremental diag coverage scan.

기존 시점(`--since-sha`) 이후 **변경된 파일만** 스캔하여, 새로 생긴
mutation API 호출 중 diag 태그가 없는 것을 찾는다.

Usage:
  python3 coverage_scan.py --since-sha <sha>                # 증분
  python3 coverage_scan.py --full                           # 전체 (baseline용)
  python3 coverage_scan.py --since-sha HEAD --known-gaps state.json  # 억제 리스트 반영
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 모니터 대상 패턴
FRONTEND_API_PATTERN = re.compile(
    r"(api\.(post|put|delete|patch)|reservationsAPI\.(create|update|delete|assignRoom|updateDailyInfo))\s*\("
)
FRONTEND_TAG_PATTERN = re.compile(r"window\.__diagAction\s*=")

BACKEND_MUTATION_ROUTE = re.compile(
    r'@router\.(post|put|delete|patch)\s*\(\s*"([^"]+)"'
)
BACKEND_DIAG_CALL = re.compile(r"\bdiag\(")

# 스캔 대상 글롭
FRONTEND_GLOB = "frontend/src/**/*.tsx"
BACKEND_GLOB = "backend/app/api/**/*.py"


def changed_files(since_sha: str) -> list[Path]:
    """since_sha..HEAD 구간에 바뀐 파일 (frontend/.tsx + backend/api/*.py 한정)"""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{since_sha}..HEAD"],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT,
    )
    paths = []
    for line in result.stdout.splitlines():
        p = REPO_ROOT / line
        if not p.exists():
            continue
        if line.startswith("frontend/src/") and line.endswith(".tsx"):
            paths.append(p)
        elif line.startswith("backend/app/api/") and line.endswith(".py"):
            paths.append(p)
    return paths


def all_target_files() -> list[Path]:
    """전체 스캔 대상"""
    files = list((REPO_ROOT / "frontend/src").rglob("*.tsx"))
    files += list((REPO_ROOT / "backend/app/api").rglob("*.py"))
    return files


def scan_frontend(path: Path) -> list[dict]:
    """프론트 파일에서 태그 없는 API 호출 지점 찾기.

    휴리스틱: 같은 파일에서 API 호출 라인 앞 20줄 이내에 __diagAction 할당이
    없으면 태그 누락으로 본다.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return []

    # 태그 할당이 있는 라인 번호 수집
    tag_lines = [i + 1 for i, line in enumerate(lines) if FRONTEND_TAG_PATTERN.search(line)]

    gaps = []
    for i, line in enumerate(lines, start=1):
        if not FRONTEND_API_PATTERN.search(line):
            continue
        # path wrapper 정의 자체는 제외 (api.ts)
        if "services/api.ts" in str(path):
            continue
        # 직전 20줄 안에 태그 할당이 있나?
        has_nearby_tag = any(t for t in tag_lines if 0 < i - t <= 20)
        if not has_nearby_tag:
            gaps.append({
                "file": str(path.relative_to(REPO_ROOT)),
                "line": i,
                "code": line.strip()[:120],
                "kind": "frontend_untagged_api",
            })
    return gaps


def scan_backend(path: Path) -> list[dict]:
    """백엔드 라우터 함수가 mutation 인데 diag 호출이 없으면 누락으로 본다.

    휴리스틱: @router.post/put/delete/patch 데코레이터 다음의 함수 본체 안에
    `diag(` 가 하나도 없으면 gap.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    gaps = []
    # 함수 블록 대강 분리 — 연속된 `@router.` 부터 다음 `@router.` 또는 파일 끝까지
    chunks = re.split(r"(?=@router\.)", text)
    for chunk in chunks:
        if not chunk.startswith("@router."):
            continue
        m = BACKEND_MUTATION_ROUTE.search(chunk)
        if not m:
            continue
        method, route = m.group(1), m.group(2)
        if not BACKEND_DIAG_CALL.search(chunk):
            # 청크의 첫 줄 줄번호 계산
            offset = text.index(chunk)
            line_no = text[:offset].count("\n") + 1
            gaps.append({
                "file": str(path.relative_to(REPO_ROOT)),
                "line": line_no,
                "code": f'@router.{method}("{route}")',
                "kind": "backend_mutation_no_diag",
            })
    return gaps


def load_suppressions(state_path: Path) -> set:
    """state.json 의 known_gaps 필드 — `file:line` 형태 set 반환"""
    if not state_path.exists():
        return set()
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {f"{g['file']}:{g['line']}" for g in data.get("known_gaps", [])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--since-sha", help="이 SHA 이후 변경 파일만 (증분)")
    p.add_argument("--full", action="store_true", help="전체 스캔")
    p.add_argument("--known-gaps", default=str(REPO_ROOT / "docs/diag-golden/state.json"),
                   help="known_gaps 억제 리스트 (state.json 경로)")
    p.add_argument("--output", default="-")
    args = p.parse_args()

    if args.full:
        files = all_target_files()
        mode = "full"
    elif args.since_sha:
        files = changed_files(args.since_sha)
        mode = f"incremental since {args.since_sha}"
    else:
        p.error("--full 또는 --since-sha 중 하나 필요")

    suppressions = load_suppressions(Path(args.known_gaps))

    all_gaps = []
    for f in files:
        if str(f).endswith(".tsx"):
            all_gaps.extend(scan_frontend(f))
        elif str(f).endswith(".py"):
            all_gaps.extend(scan_backend(f))

    # 억제 적용
    filtered = [g for g in all_gaps if f"{g['file']}:{g['line']}" not in suppressions]

    report = {
        "mode": mode,
        "files_scanned": len(files),
        "total_gaps": len(all_gaps),
        "suppressed": len(all_gaps) - len(filtered),
        "gaps": filtered,
    }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(text)
    else:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"✓ {args.output} 에 저장 — 총 {len(filtered)}건 (suppressed {report['suppressed']})",
              file=sys.stderr)


if __name__ == "__main__":
    main()
