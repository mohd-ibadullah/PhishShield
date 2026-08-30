"""§4.5 Concurrency stress test for scan_logs.jsonl writes.

Writes N records concurrently from multiple threads, then asserts every
line parses as valid JSON and the count matches exactly.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from conftest import app, BACKEND_DIR

N_RECORDS = 200
N_THREADS = 20


def _make_record(i: int) -> dict:
    return {
        "scan_id": f"conc-{i}-{uuid.uuid4().hex[:8]}",
        "cached": False,
        "signals": [f"signal-{i}"],
        "safe_signals": [],
        "risk_score": i % 100,
        "verdict": "Safe",
        "confidence": 60,
    }


def test_concurrent_jsonl_writes(tmp_path) -> None:
    """Write N_RECORDS concurrently, assert every line parses and count matches."""
    jsonl_path = tmp_path / "scan_logs_concurrency_test.jsonl"

    import importlib
    main_mod = importlib.import_module("main")
    # Patch the path to use our tmp test file
    original_path = main_mod.SCAN_LOG_PATH
    main_mod.SCAN_LOG_PATH = jsonl_path

    errors: list[str] = []
    barrier = threading.Barrier(N_THREADS)

    def writer(start: int) -> None:
        try:
            barrier.wait()
            for i in range(start, start + N_RECORDS // N_THREADS):
                main_mod.append_structured_scan_log(_make_record(i))
        except Exception as e:
            errors.append(f"Thread error: {e}")

    threads = [threading.Thread(target=writer, args=(i * N_RECORDS // N_THREADS,))
               for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Thread errors: {errors}"

    # Read back and verify
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    parse_ok = 0
    parse_fail = 0
    for line in lines:
        s = line.strip()
        if not s:
            parse_fail += 1
            continue
        try:
            json.loads(s)
            parse_ok += 1
        except json.JSONDecodeError:
            parse_fail += 1

    assert parse_ok == N_RECORDS, (
        f"Expected {N_RECORDS} parsed lines, got {parse_ok} (parse_fail={parse_fail}, total={len(lines)})"
    )
    assert parse_fail == 0, (
        f"Parse failures under concurrency: {parse_fail}/{len(lines)}"
    )

    # Cleanup
    main_mod.SCAN_LOG_PATH = original_path
