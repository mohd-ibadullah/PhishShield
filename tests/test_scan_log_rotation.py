"""T4b: JSONL rotation tests."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as bm


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path):
    """Point SCAN_LOG_PATH to a temp file for each test."""
    log_path = tmp_path / "scan_logs.jsonl"
    original = bm.SCAN_LOG_PATH
    bm.SCAN_LOG_PATH = log_path
    yield log_path
    bm.SCAN_LOG_PATH = original


def _write_line(handle):
    entry = {"timestamp": "2026-01-01T00:00:00", "scan_id": "test", "verdict": "Safe"}
    line = json.dumps(entry) + "\n"
    handle.write(line)
    handle.flush()


def test_rotates_at_size(tmp_path):
    """When file exceeds LOG_MAX_BYTES, rotation creates .1 and truncates.

    Payload stays within cap*(KEEP+1)=800 so the archive survives the
    total-chain cap (B1).
    """
    bm.LOG_MAX_BYTES = 200  # very small for testing
    bm.LOG_KEEP = 3
    log_path = tmp_path / "scan_logs.jsonl"

    # Write enough to exceed 200 bytes
    with open(log_path, "w", encoding="utf-8") as f:
        for _ in range(5):
            _write_line(f)

    # Trigger rotation check by writing one more via the function
    entry = {"timestamp": "2026-01-01T00:00:00", "scan_id": "trigger", "verdict": "Safe"}
    violations = bm.validate_record(entry)
    if not violations:
        bm.append_structured_scan_log(entry)

    # .1 should exist
    assert (tmp_path / "scan_logs.jsonl.1").exists(), "Rotation did not create .1"


def test_keeps_only_3_files(tmp_path):
    """Rotation never keeps more than LOG_KEEP rotated files."""
    bm.LOG_MAX_BYTES = 100
    bm.LOG_KEEP = 3
    log_path = tmp_path / "scan_logs.jsonl"

    # Simulate many rotations by creating files (empty archives keep the chain
    # within cap*(KEEP+1)=400 under the total-chain cap, B1).
    for i in range(1, 7):
        p = tmp_path / f"scan_logs.jsonl.{i}"
        p.write_text("", encoding="utf-8")

    # Write enough to current file (4 lines ~300 B + trigger 75 B > cap 100,
    # chain stays <= 400)
    with open(log_path, "w", encoding="utf-8") as f:
        for _ in range(4):
            _write_line(f)

    # Trigger rotation
    entry = {"timestamp": "2026-01-01T00:00:00", "scan_id": "trigger2", "verdict": "Safe"}
    violations = bm.validate_record(entry)
    if not violations:
        bm.append_structured_scan_log(entry)

    # Only .1, .2, .3 should exist
    for i in range(1, 4):
        assert (tmp_path / f"scan_logs.jsonl.{i}").exists(), f".{i} missing"
    for i in range(4, 7):
        assert not (tmp_path / f"scan_logs.jsonl.{i}").exists(), f".{i} should have been dropped"


def test_rotation_caps_total_chain(tmp_path):
    """B1: the total scan_logs.jsonl* chain stays <= LOG_MAX_BYTES * (LOG_KEEP + 1)."""
    import glob

    bm.LOG_MAX_BYTES = 200
    bm.LOG_KEEP = 3
    log_path = tmp_path / "scan_logs.jsonl"

    # Build a chain whose combined size far exceeds cap * (KEEP + 1) = 800.
    with open(log_path, "w", encoding="utf-8") as f:
        for _ in range(40):
            _write_line(f)
    for i in range(1, 5):
        p = tmp_path / f"scan_logs.jsonl.{i}"
        p.write_text("old data\n" * 60, encoding="utf-8")  # ~540 B each

    # Trigger rotation via the real writer.
    entry = {"timestamp": "2026-01-01T00:00:00", "scan_id": "chain-cap", "verdict": "Safe"}
    violations = bm.validate_record(entry)
    if not violations:
        bm.append_structured_scan_log(entry)

    total = sum(os.path.getsize(p) for p in glob.glob(str(tmp_path / "scan_logs.jsonl*")))
    assert total <= bm.LOG_MAX_BYTES * (bm.LOG_KEEP + 1), f"chain total {total} > cap 800"
    # The live file alone must never exceed the cap either (it may not exist
    # after a flush that dropped every archive).
    if os.path.exists(log_path):
        assert os.path.getsize(log_path) <= bm.LOG_MAX_BYTES, f"live file {os.path.getsize(log_path)} > cap"


def test_rotation_preserves_no_content(tmp_path):
    """After rotation, newly written lines must have no raw content in input_preview.

    Payload stays within cap*(KEEP+1)=800 so the .1 archive survives the
    total-chain cap (B1).
    """
    bm.LOG_MAX_BYTES = 200
    bm.LOG_KEEP = 3
    log_path = tmp_path / "scan_logs.jsonl"

    # Write raw content to simulate pre-fix (4 lines ~450 B > cap 200 -> rotation)
    with open(log_path, "w", encoding="utf-8") as f:
        for _ in range(4):
            entry = {"timestamp": "2026-01-01", "scan_id": "raw", "input_preview": "From: user1@example.invalid Subject: Urgent"}
            f.write(json.dumps(entry) + "\n")

    # Trigger rotation
    entry = {"timestamp": "2026-01-01T00:00:00", "scan_id": "clean", "verdict": "Safe"}
    violations = bm.validate_record(entry)
    if not violations:
        bm.append_structured_scan_log(entry)

    # After rotation, check .1 for raw content and current file for clean
    import re
    RAW = re.compile(r"(?i)^(from|subject|to|received|return-path|authentication-results):")
    # .1 should have the raw content (pre-fix data)
    rotated = tmp_path / "scan_logs.jsonl.1"
    assert rotated.exists(), "Rotated file .1 should exist"
    # Current file (if exists) must have 0 content lines
    if log_path.exists():
        content_count = 0
        for line in open(log_path, encoding="utf-8", errors="replace"):
            try:
                rec = json.loads(line)
                p = rec.get("input_preview", "")
                if p and any(RAW.match(x) for x in str(p).splitlines()):
                    content_count += 1
            except Exception:
                pass
        assert content_count == 0, f"Newly written file has {content_count} content lines"