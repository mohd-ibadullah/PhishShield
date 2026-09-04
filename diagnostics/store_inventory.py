#!/usr/bin/env python3
"""Key inventory for every persisted store.  Read-only — never modifies data.

Usage:
    python diagnostics/store_inventory.py

Reports, for each store:
  - Union of top-level keys across a sample (first/last/random)
  - Per-key full-file count
  - For JSON columns in SQLite: nested key union + per-key count
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import random
import sqlite3
import sys
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATA = ROOT / "data"

# ── helpers ──────────────────────────────────────────────────

def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _file_info(p: pathlib.Path) -> dict[str, Any]:
    st = p.stat()
    return {"size_bytes": st.st_size, "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))}


def _sample_indices(total: int, sample_n: int = 600) -> list[int]:
    """First 50 + last 50 + random up to sample_n total."""
    if total <= sample_n:
        return list(range(total))
    indices = set(range(50)) | set(range(total - 50, total))
    remaining = sample_n - len(indices)
    if remaining > 0:
        pool = list(range(50, total - 50))
        indices |= set(random.sample(pool, min(remaining, len(pool))))
    return sorted(indices)


def _discover_and_count_jsonl(path: pathlib.Path, key_filter: set[str] | None = None
                               ) -> dict[str, Any]:
    """Scan a JSONL file, discover keys from sample, then count all keys across full file."""
    info = _file_info(path)
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    total_lines = len(raw_lines)
    t_start = time.time()

    # Phase 1: discover keys from sample
    sample_idx = _sample_indices(total_lines)
    discovered_keys: set[str] = set()
    parsed_sample = 0
    for i in sample_idx:
        line = raw_lines[i].strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                discovered_keys.update(obj.keys())
            parsed_sample += 1
        except json.JSONDecodeError:
            pass

    # Phase 2: full-file count per discovered key
    key_counts = collections.Counter()
    parse_ok = 0
    parse_fail = 0
    for line in raw_lines:
        line_s = line.strip()
        if not line_s:
            parse_fail += 1
            continue
        try:
            obj = json.loads(line_s)
            parse_ok += 1
            if isinstance(obj, dict):
                for k in obj:
                    key_counts[k] += 1
        except json.JSONDecodeError:
            parse_fail += 1

    elapsed = time.time() - t_start
    return {
        "path": str(path),
        "info": info,
        "total_lines": total_lines,
        "parsed": parse_ok,
        "parse_fail": parse_fail,
        "discovered_keys_sample": sorted(discovered_keys),
        "key_counts": dict(key_counts.most_common()),
        "elapsed_s": round(elapsed, 2),
        "measured_at": _ts(),
    }


def _scan_sqlite_db(path: pathlib.Path) -> dict[str, Any]:
    """Inventory every table and every JSON column in a SQLite database."""
    info = _file_info(path)
    db = sqlite3.connect(str(path))
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    result: dict[str, Any] = {"path": str(path), "info": info, "tables": {}, "measured_at": _ts()}

    for tname in tables:
        cols = [r[1] for r in db.execute(f"PRAGMA table_info([{tname}])").fetchall()]
        row_count = db.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]

        # Discover which columns contain JSON
        json_cols: dict[str, set[str]] = {}
        sample_rows = db.execute(f"SELECT * FROM [{tname}] LIMIT 50").fetchall()
        for row in sample_rows:
            for ci, val in enumerate(row):
                if isinstance(val, str) and val.strip().startswith("{"):
                    try:
                        obj = json.loads(val)
                        if isinstance(obj, dict):
                            json_cols.setdefault(cols[ci], set()).update(obj.keys())
                    except json.JSONDecodeError:
                        pass

        # Full-file counts for JSON columns
        json_col_counts: dict[str, dict[str, int]] = {}
        for jcol, jkeys in json_cols.items():
            counts: dict[str, int] = collections.Counter()
            all_rows = db.execute(f"SELECT [{jcol}] FROM [{tname}]").fetchall()
            for (val,) in all_rows:
                if not isinstance(val, str):
                    continue
                try:
                    obj = json.loads(val)
                    if isinstance(obj, dict):
                        for k in obj:
                            counts[k] += 1
                except json.JSONDecodeError:
                    counts["__PARSE_ERROR__"] += 1
            json_col_counts[jcol] = {"discovered_keys": sorted(jkeys), "counts": dict(counts.most_common())}

        result["tables"][tname] = {
            "columns": cols,
            "row_count": row_count,
            "json_columns": json_col_counts,
        }

    db.close()
    return result


def _scan_csv(path: pathlib.Path) -> dict[str, Any]:
    """Header-only inventory for CSV files."""
    if not path.exists():
        return {"path": str(path), "exists": False}
    info = _file_info(path)
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip()
    return {"path": str(path), "info": info, "header": header, "measured_at": _ts()}


def _scan_json_flat(path: pathlib.Path) -> dict[str, Any]:
    """Top-level key inventory for flat JSON files."""
    if not path.exists():
        return {"path": str(path), "exists": False}
    info = _file_info(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        keys = sorted(data.keys())
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        keys = sorted(set().union(*(d.keys() for d in data[:10])))
    else:
        keys = []
    return {"path": str(path), "info": info, "top_keys": keys, "measured_at": _ts()}


# ── main ─────────────────────────────────────────────────────

def main() -> None:
    stores = [
        ("scan_logs.jsonl", _discover_and_count_jsonl, BACKEND / "scan_logs.jsonl"),
        ("scans.db", _scan_sqlite_db, BACKEND / "scans.db"),
        ("feedback.csv", _scan_csv, DATA / "feedback.csv"),
        ("feedback_memory.json", _scan_json_flat, DATA / "feedback_memory.json"),
        ("sender_profiles.json", _scan_json_flat, BACKEND / "sender_profiles.json"),
    ]

    for name, fn, path in stores:
        print(f"\n{'='*60}")
        print(f"STORE: {name}")
        print(f"{'='*60}")
        result = fn(path)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
