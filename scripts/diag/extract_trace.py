#!/usr/bin/env python3
"""
Extract a normalized diag trace from refactor-diag.log for a specific req_id
or time range. Output is JSON suitable for feeding into diff_trace.py.

Usage:
  python3 extract_trace.py --log <file> --req <req_id>
  python3 extract_trace.py --log <file> --since "2026-04-21 13:30:00"
  python3 extract_trace.py --log <file> --req <req_id> --today 2026-04-21
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta

EVENT_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s+\|\s+INFO\s+\|\s+\[(?P<event>[\w.]+)\]\s*(?P<rest>.*)$"
)
KV_PATTERN = re.compile(r"(\w+)=(\S+)")

NUMERIC_ID_FIELDS = {
    "res_id", "reservation_id", "room_id", "member_res_id", "pushed_res_id",
    "caused_by", "tenant_id", "tid", "schedule_id", "target_id", "group_id",
}
DROP_ALWAYS = {"ms"}
MASK_PARTIAL = {"to"}  # 전화번호 필드: 이미 마스킹된 상태 유지


def normalize_date(value: str, today: str) -> str:
    """절대 날짜 → 상대 표현."""
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
        t = datetime.strptime(today, "%Y-%m-%d").date()
        diff = (d - t).days
        if diff == 0:
            return "today"
        if diff > 0:
            return f"today+{diff}"
        return f"today{diff}"  # diff가 음수라 이미 -기호 포함
    except ValueError:
        return value


def normalize_action(value: str) -> str:
    """action=drag_guest_to_room:res=4077,room=B308 → drag_guest_to_room"""
    return value.split(":", 1)[0]


def parse_line(line: str, today: str):
    m = EVENT_LINE.match(line)
    if not m:
        return None
    ts = m.group("ts")
    event = m.group("event")
    rest = m.group("rest")

    kv = dict(KV_PATTERN.findall(rest))
    req_id = kv.get("req", "-")
    action_raw = kv.get("action")

    # 정규화
    normalized_fields = {}
    for k, v in kv.items():
        if k in DROP_ALWAYS:
            continue
        if k == "req":
            continue  # req_id 는 별도 필드로
        if k == "action":
            normalized_fields["action_prefix"] = normalize_action(v)
            continue
        if k in NUMERIC_ID_FIELDS:
            normalized_fields[k] = "*"  # 비교 시 와일드카드
            continue
        # 날짜 필드 상대화
        if k in ("from_date", "end_date", "date", "check_in", "check_out",
                 "target_date", "original_from", "clamped_to", "today"):
            normalized_fields[k] = normalize_date(v, today)
            continue
        normalized_fields[k] = v

    return {
        "timestamp": ts,
        "event": event,
        "req_id": req_id,
        "fields": normalized_fields,
        "raw_line": line.rstrip(),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log", required=True, help="refactor-diag.log 경로")
    p.add_argument("--req", help="특정 req_id 만 추출")
    p.add_argument("--since", help="이 타임스탬프 이후만 추출 (YYYY-MM-DD HH:MM:SS)")
    p.add_argument("--today", default=datetime.now().strftime("%Y-%m-%d"),
                   help="상대 날짜 계산 기준일 (기본: 오늘)")
    p.add_argument("--output", default="-", help="출력 파일 (- = stdout)")
    args = p.parse_args()

    events = []
    with open(args.log, encoding="utf-8") as f:
        for line in f:
            parsed = parse_line(line, args.today)
            if not parsed:
                continue
            if args.since and parsed["timestamp"] < args.since:
                continue
            if args.req and parsed["req_id"] != args.req:
                continue
            events.append(parsed)

    out = {
        "today": args.today,
        "filter": {"req": args.req, "since": args.since},
        "count": len(events),
        "events": events,
    }

    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(text)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✓ {args.output} 에 {len(events)}개 이벤트 저장", file=sys.stderr)


if __name__ == "__main__":
    main()
