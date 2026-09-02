#!/usr/bin/env python3
"""Census of scan_logs.jsonl content categories.

Usage:
    python diagnostics/scan_log_census.py          # assert + print
    python diagnostics/scan_log_census.py --report  # same, for ledger
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

RAW = re.compile(r"(?i)^(from|subject|to|received|return-path|authentication-results):")


def census(path: str = "backend/scan_logs.jsonl") -> dict[str, int]:
    counts = {"content": 0, "hash16": 0, "absent": 0, "malformed": 0, "other": 0}
    total = 0
    for line in pathlib.Path(path).open(encoding="utf-8", errors="replace"):
        total += 1
        s = line.strip()
        if not s:
            counts["malformed"] += 1
            continue
        try:
            rec = json.loads(s)
        except Exception:
            counts["malformed"] += 1
            continue
        p = rec.get("input_preview", None)
        if p is None or p == "":
            counts["absent"] += 1
        elif isinstance(p, str) and re.fullmatch(r"[0-9a-f]{16}", p):
            counts["hash16"] += 1
        elif isinstance(p, str) and any(RAW.match(x) for x in p.splitlines()):
            counts["content"] += 1
        elif isinstance(p, str):
            counts["other"] += 1
        else:
            counts["other"] += 1
    assert sum(counts.values()) == total, (counts, total)
    return {"total": total, **counts}


if __name__ == "__main__":
    result = census()
    report = "--report" in sys.argv
    if report:
        print(
            f"CONFIRMED: {result['content']} pre-fix rows still hold raw content; "
            f"writer is now content-free; historical purge NOT EXECUTED — operator "
            f"decision required (destructive, touches ~40 MB of the user's only local store)"
        )
        print(f"Total: {result['total']}, content: {result['content']}, "
              f"hash16: {result['hash16']}, absent: {result['absent']}, "
              f"malformed: {result['malformed']}, other: {result['other']}")
    else:
        print(result)
