#!/usr/bin/env python3
"""Remove VIOLATION-PROOF marker lines from scan_logs.jsonl.

Predicate-based: selects by marker string, not by line count.
Original file is kept; cleaned copy written to a sibling file.

Safety checks:
  1. Pre-flight: re-measure file size, abort if it differs from the
     size observed at script start (another process may have appended).
  2. Pre-flight: count matching lines, abort if count differs from
     the count observed at script start.
  3. Idempotent: running twice produces the same result (0 matches).

Usage:
  python scripts/remove_violation_markers.py --dry-run
  python scripts/remove_violation_markers.py --execute
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_FILE = REPO_ROOT / "backend" / "scan_logs.jsonl"
CLEANED_FILE = STORE_FILE.with_suffix(".jsonl.cleaned")
MARKER_PATTERN = "VIOLATION-PROOF"


def count_marker_lines(path: Path) -> int:
    """Count lines containing the marker pattern."""
    count = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if MARKER_PATTERN in line:
                count += 1
    return count


def count_total_lines(path: Path) -> int:
    """Count all lines."""
    count = 0
    with open(path, "rb") as f:
        for _ in f:
            count += 1
    return count


def file_size(path: Path) -> int:
    return path.stat().st_size


def file_hash(path: Path) -> str:
    """SHA-256 of the file content."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without modifying any file."
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually write the cleaned file."
    )
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("Specify --dry-run or --execute")

    if not STORE_FILE.exists():
        print(f"ERROR: {STORE_FILE} does not exist", file=sys.stderr)
        sys.exit(1)

    # ── Step 1: pre-flight measurement ──
    t0 = time.monotonic()
    initial_size = file_size(STORE_FILE)
    initial_lines = count_total_lines(STORE_FILE)
    initial_markers = count_marker_lines(STORE_FILE)
    initial_hash = file_hash(STORE_FILE)
    t_measure = time.monotonic() - t0

    print(f"Pre-flight measurement ({t_measure*1000:.0f} ms):")
    print(f"  File: {STORE_FILE}")
    print(f"  Size: {initial_size} bytes ({initial_size/1024/1024:.1f} MB)")
    print(f"  Total lines: {initial_lines}")
    print(f"  Lines matching '{MARKER_PATTERN}': {initial_markers}")
    print(f"  SHA-256: {initial_hash[:16]}...")
    print()

    if initial_markers == 0:
        print("No marker lines found. Nothing to do. (Idempotent: already clean.)")
        sys.exit(0)

    # ── Step 2: re-measure and verify size hasn't changed ──
    t1 = time.monotonic()
    current_size = file_size(STORE_FILE)
    current_markers = count_marker_lines(STORE_FILE)
    t_verify = time.monotonic() - t1

    if current_size != initial_size:
        print(
            f"ABORT: file size changed between measurements "
            f"({initial_size} → {current_size}). "
            f"Another process may have appended. Re-run.",
            file=sys.stderr,
        )
        sys.exit(2)

    if current_markers != initial_markers:
        print(
            f"ABORT: marker count changed between measurements "
            f"({initial_markers} → {current_markers}). "
            f"Re-run.",
            file=sys.stderr,
        )
        sys.exit(3)

    print(f"Pre-flight verification ({t_verify*1000:.0f} ms): size and marker count stable.")
    print()

    # ── Step 3: filter ──
    kept = 0
    removed = 0

    if args.dry_run:
        print("DRY RUN — would write cleaned file to:")
        print(f"  {CLEANED_FILE}")
        print()
        # Count what would be kept/removed
        with open(STORE_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if MARKER_PATTERN in line:
                    removed += 1
                    print(f"  WOULD REMOVE: {line.rstrip()[:120]}")
                else:
                    kept += 1
        print()
        print(f"DRY RUN summary: {kept} kept, {removed} removed, {kept + removed} total.")
        print(f"Original file preserved: {STORE_FILE}")
        print(f"Would-create file: {CLEANED_FILE}")
        sys.exit(0)

    # ── Execute: write cleaned file ──
    with open(STORE_FILE, "r", encoding="utf-8", errors="replace") as fin, \
         open(CLEANED_FILE, "w", encoding="utf-8") as fout:
        for line in fin:
            if MARKER_PATTERN in line:
                removed += 1
            else:
                fout.write(line)
                kept += 1

    cleaned_size = file_size(CLEANED_FILE)
    cleaned_lines = count_total_lines(CLEANED_FILE)
    cleaned_hash = file_hash(CLEANED_FILE)

    print(f"Cleaned file written: {CLEANED_FILE}")
    print(f"  Size: {cleaned_size} bytes")
    print(f"  Lines: {cleaned_lines}")
    print(f"  SHA-256: {cleaned_hash[:16]}...")
    print(f"  Kept: {kept}, Removed: {removed}")
    print()
    print(f"Original preserved: {STORE_FILE} ({initial_size} bytes, {initial_lines} lines)")
    print()
    print(f"Lines removed ({removed}) + lines kept ({kept}) = {removed + kept}")
    print(f"Original line count: {initial_lines}")
    print(f"Non-marker line count preserved: {kept == initial_lines - removed}")
    print()

    # ── Step 4: verify idempotency ──
    cleaned_markers = count_marker_lines(CLEANED_FILE)
    print(f"Idempotency check: markers in cleaned file = {cleaned_markers} (expected 0)")

    if cleaned_markers != 0:
        print("ERROR: cleaned file still contains markers!", file=sys.stderr)
        sys.exit(4)

    print()
    print("DONE. Original kept, cleaned copy ready for operator review.")
    print("To apply: rename cleaned → original after verifying.")


if __name__ == "__main__":
    main()
