#!/usr/bin/env python3
"""
Compare an actual extracted trace (JSON from extract_trace.py) against a golden
trace (YAML in docs/diag-golden/actions/).

Usage:
  python3 diff_trace.py <golden.yaml> --actual-json <trace.json>
  python3 diff_trace.py <golden.yaml> --actual-log <log> --req <id> --today 2026-04-21
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML 필요. pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def field_match(expected, actual) -> bool:
    """'*' 는 단독/내장 모두 와일드카드. glob 스타일 매칭."""
    if isinstance(expected, bool):
        return str(actual).lower() == str(expected).lower()
    exp_str = str(expected)
    if exp_str == "*":
        return True
    if "*" in exp_str:
        import fnmatch
        return fnmatch.fnmatchcase(str(actual), exp_str)
    return str(actual) == exp_str


def match_mandatory(golden_event, actual_event) -> list:
    """이벤트 이름 + 필드값 일치 확인. 불일치 필드 목록 반환."""
    diffs = []
    if golden_event["event"] != actual_event["event"]:
        return [f"event name differs: expected={golden_event['event']} actual={actual_event['event']}"]
    expected_fields = golden_event.get("fields", {}) or {}
    for k, v in expected_fields.items():
        actual_v = actual_event["fields"].get(k)
        if actual_v is None:
            diffs.append(f"missing field {k} (expected={v})")
        elif not field_match(v, actual_v):
            diffs.append(f"field {k}: expected={v} actual={actual_v}")
    return diffs


def compare(golden: dict, actual_events: list) -> dict:
    """정답지 vs 실제 이벤트 시퀀스."""
    result = {
        "passed": True,
        "mandatory_diffs": [],
        "variable_count_diffs": [],
        "forbidden_hits": [],
        "matched_pairs": 0,
    }

    # 1. FORBIDDEN 이벤트가 찍혔는지 먼저 체크
    forbidden = {f.get("event"): f.get("reason", "") for f in (golden.get("forbidden_events") or [])}
    for ae in actual_events:
        if ae["event"] in forbidden:
            result["forbidden_hits"].append({
                "event": ae["event"],
                "reason": forbidden[ae["event"]],
                "at": ae["timestamp"],
            })
            result["passed"] = False

    # 2. MANDATORY 순서대로 매칭 (그리디, 순서 유지)
    expected = golden.get("expected_trace", []) or []
    actual_idx = 0
    actual_n = len(actual_events)

    for exp in expected:
        cat = exp.get("category", "MANDATORY")
        ev_name = exp["event"]

        if cat == "MANDATORY":
            # actual 에서 다음 해당 이벤트 찾음
            found = False
            while actual_idx < actual_n:
                ae = actual_events[actual_idx]
                actual_idx += 1
                if ae["event"] == ev_name:
                    diffs = match_mandatory(exp, ae)
                    if diffs:
                        result["mandatory_diffs"].append({"event": ev_name, "diffs": diffs})
                        result["passed"] = False
                    else:
                        result["matched_pairs"] += 1
                    found = True
                    break
            if not found:
                result["mandatory_diffs"].append({"event": ev_name, "diffs": ["MISSING"]})
                result["passed"] = False

        elif cat == "VARIABLE_COUNT":
            min_n = exp.get("min", 1)
            count = sum(1 for ae in actual_events if ae["event"] == ev_name)
            if count < min_n:
                result["variable_count_diffs"].append({
                    "event": ev_name, "expected_min": min_n, "actual": count,
                })
                result["passed"] = False

        elif cat == "CONDITIONAL":
            # 조건부는 스킵 — when 은 자연어라 사람 판단 필요
            pass

    return result


def format_report(golden_path: str, golden: dict, result: dict) -> str:
    lines = []
    status = "✅ PASS" if result["passed"] else "❌ DIFF"
    lines.append(f"{status}  {golden_path}")
    lines.append(f"  action: {golden.get('action', '(미지정)')}")
    lines.append(f"  matched MANDATORY: {result['matched_pairs']}")

    if result["forbidden_hits"]:
        lines.append("\n  🚫 FORBIDDEN 이벤트 출현:")
        for h in result["forbidden_hits"]:
            lines.append(f"    - {h['event']} @ {h['at']}")
            if h["reason"]:
                lines.append(f"      사유: {h['reason']}")

    if result["mandatory_diffs"]:
        lines.append("\n  ⚠️  MANDATORY 불일치:")
        for d in result["mandatory_diffs"]:
            lines.append(f"    - {d['event']}: {'; '.join(d['diffs'])}")

    if result["variable_count_diffs"]:
        lines.append("\n  ⚠️  VARIABLE_COUNT 미달:")
        for d in result["variable_count_diffs"]:
            lines.append(f"    - {d['event']}: expected min {d['expected_min']}, got {d['actual']}")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("golden", help="docs/diag-golden/actions/*.yaml")
    p.add_argument("--actual-json", help="extract_trace.py 가 만든 JSON")
    p.add_argument("--actual-log", help="또는 로그 파일 직접 지정")
    p.add_argument("--req", help="--actual-log 와 함께, req_id 지정")
    p.add_argument("--today", help="--actual-log 와 함께, 상대 날짜 기준일")
    args = p.parse_args()

    with open(args.golden, encoding="utf-8") as f:
        golden = yaml.safe_load(f)

    if args.actual_json:
        with open(args.actual_json, encoding="utf-8") as f:
            actual_data = json.load(f)
    elif args.actual_log and args.req:
        extract_script = Path(__file__).parent / "extract_trace.py"
        cmd = ["python3", str(extract_script), "--log", args.actual_log, "--req", args.req]
        if args.today:
            cmd += ["--today", args.today]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        actual_data = json.loads(out.stdout)
    else:
        p.error("--actual-json 또는 --actual-log + --req 중 하나 필요")

    result = compare(golden, actual_data["events"])
    print(format_report(args.golden, golden, result))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
