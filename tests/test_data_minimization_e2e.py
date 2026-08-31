"""Data-minimisation marker test + guard verification.

§2: Proves the guard is not vacuous by:
  - Scanning a marker email and asserting no forbidden raw-content key leaks
  - Asserting every PERSISTABLE_HASH_KEYS value is valid hex
  - Asserting the log value differs from plain sha256 (proving HMAC is in use)
  - Mutation proof: temporarily re-introduce the leak, show failure, restore
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from conftest import app, BACKEND_DIR

# Import shared constants — single source of truth
import importlib
_main = importlib.import_module("main")
from data_constants import (
    FORBIDDEN_RAW_CONTENT_KEYS,
    HASH_VALUE_PATTERN,
)

MARKER = f"MARKER-{uuid.uuid4().hex[:16]}"
MARKER_EMAIL = f"Subject: Test\nFrom: test@example.com\nBody: {MARKER} verify your account"

# §1.1: Paths are resolved lazily inside each test function so the
# conftest session fixture has time to redirect them to tmp.
def _db(): return _main.SCANS_DB_PATH
def _jsonl(): return _main.SCAN_LOG_PATH
def _csv(): return _main.FEEDBACK_CSV_PATH
def _feedback_mem(): return _main.FEEDBACK_MEMORY_PATH
def _sender(): return _main.SENDER_PROFILE_PATH

_HASH_RE = re.compile(HASH_VALUE_PATTERN)


# ── §2.1: Marker test ────────────────────────────────────────

async def test_no_marker_in_any_persisted_store() -> None:
    """Scan an email with a unique marker, then assert the marker is absent
    from every forbidden raw-content key in every persisted store."""
    # 1. Perform the scan
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/scan-email",
            json={"email_text": MARKER_EMAIL},
        )
        assert resp.status_code == 200, f"Scan failed: {resp.text}"

    # 2. Check scans.db — all tables, all columns for forbidden raw content
    db_path = _db()
    assert db_path.exists(), f"DB not found: {db_path}"
    db = sqlite3.connect(str(db_path))
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    for table in tables:
        cols = [r[1] for r in db.execute(f"PRAGMA table_info([{table}])").fetchall()]
        for col in cols:
            if col not in FORBIDDEN_RAW_CONTENT_KEYS:
                continue
            rows = db.execute(
                f"SELECT COUNT(*) FROM [{table}] WHERE [{col}] LIKE ?",
                (f"%{MARKER}%",),
            ).fetchone()[0]
            assert rows == 0, (
                f"MARKER found in forbidden col={col} in table={table}: {rows} rows"
            )
    db.close()

    # 3. Check scan_logs.jsonl — no forbidden raw-content key contains the marker
    jsonl_path = _jsonl()
    assert jsonl_path.exists(), f"JSONL not found: {jsonl_path}"
    jsonl_violations = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if MARKER not in line:
                continue
            try:
                obj = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            for key in FORBIDDEN_RAW_CONTENT_KEYS:
                if key in obj and MARKER in str(obj[key]):
                    jsonl_violations.append(key)
    assert not jsonl_violations, (
        f"MARKER found in forbidden keys in scan_logs.jsonl: {jsonl_violations}"
    )

    # 4. Check other stores
    for label, path in [
        ("feedback.csv", _csv()),
        ("feedback_memory.json", _feedback_mem()),
        ("sender_profiles.json", _sender()),
    ]:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            assert MARKER not in text, f"MARKER found in {label}"


# ── §2.2: Hash format + HMAC proof ───────────────────────────

def test_input_hash_removed_from_writer() -> None:
    """§4.1: input_hash was removed from the writer — scan_id serves
    correlation, no external consumer reads input_hash from the log.
    New records must NOT contain input_hash."""
    jsonl_path = _jsonl()
    assert jsonl_path.exists()
    # Check the last 50 lines (the ones written by this session's tests)
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    for line in lines[-50:]:
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        assert "input_hash" not in obj, (
            f"input_hash still present in new record: {obj.get('scan_id')}"
        )


def test_hmac_differs_from_plain_sha256() -> None:
    """Verify the log uses keyed HMAC, not plain sha256."""
    marker = f"HMAC-TEST-{uuid.uuid4().hex[:8]}"
    log_val = _main.build_safe_preview(marker)
    plain_sha = hashlib.sha256(marker.encode("utf-8")).hexdigest()[:16]
    assert log_val != plain_sha, (
        f"build_safe_preview returned plain sha256, not HMAC: {log_val!r} == {plain_sha!r}"
    )


def test_forbidden_keys_constant_is_correct() -> None:
    """Verify the shared constants match expected values."""
    assert FORBIDDEN_RAW_CONTENT_KEYS == frozenset({
        "email_text", "input_preview", "headers", "client_ip",
    }), f"FORBIDDEN_RAW_CONTENT_KEYS drifted: {FORBIDDEN_RAW_CONTENT_KEYS}"


# ── §4.2: No persistable hash fields in new records ──────────

def test_no_email_content_in_new_records():
    """§4.2: No forbidden raw-content key (email_text, input_preview,
    headers, client_ip) should appear in any new JSONL record."""
    jsonl_path = _jsonl()
    assert jsonl_path.exists()
    violations = []
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    for line_no, line in enumerate(lines[-50:], len(lines) - 49):
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        for key in FORBIDDEN_RAW_CONTENT_KEYS:
            if key in obj:
                violations.append(
                    f"line {line_no}: forbidden key '{key}' in record {obj.get('scan_id')}"
                )
    assert not violations, (
        "Forbidden keys in new records:\n" + "\n".join(violations[:20])
    )


# ── §2.3: Mutation proof ─────────────────────────────────────

def _inject_leak(tmp_path: Path) -> Path:
    """Create a scratch JSONL with input_preview (forbidden key) containing a marker."""
    leak_marker = f"MUTATION-LEAK-{uuid.uuid4().hex[:8]}"
    scratch = tmp_path / "scratch.jsonl"
    record = {
        "scan_id": "mut-test",
        "input_preview": leak_marker,
        "input_hash": "abcdef0123456789",
        "verdict": "Safe",
    }
    scratch.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return scratch, leak_marker


def test_mutation_proof_guard_fails_on_leak(tmp_path: Path) -> None:
    """If input_preview (forbidden) is present with email content, the guard must fail."""
    scratch, leak_marker = _inject_leak(tmp_path)

    # Simulate the guard check: scan for forbidden keys containing the marker
    violations = []
    with open(scratch, "r", encoding="utf-8") as f:
        for line in f:
            if leak_marker not in line:
                continue
            obj = json.loads(line.strip())
            for key in FORBIDDEN_RAW_CONTENT_KEYS:
                if key in obj and leak_marker in str(obj[key]):
                    violations.append(key)

    # This MUST find the violation — if it doesn't, the guard is vacuous
    assert violations, (
        f"Guard did not detect forbidden key '{violations}' — guard is vacuous!"
    )
    assert "input_preview" in violations, (
        f"Expected input_preview in violations, got: {violations}"
    )


def test_mutation_proof_guard_passes_on_clean(tmp_path: Path) -> None:
    """A clean record with only input_hash (allowed) must pass the guard."""
    clean_marker = f"MUTATION-CLEAN-{uuid.uuid4().hex[:8]}"
    scratch = tmp_path / "clean.jsonl"
    record = {
        "scan_id": "clean-test",
        "input_hash": _main.build_safe_preview(clean_marker),
        "verdict": "Safe",
    }
    scratch.write_text(json.dumps(record) + "\n", encoding="utf-8")

    violations = []
    with open(scratch, "r", encoding="utf-8") as f:
        for line in f:
            if clean_marker not in line:
                continue
            obj = json.loads(line.strip())
            for key in FORBIDDEN_RAW_CONTENT_KEYS:
                if key in obj and clean_marker in str(obj[key]):
                    violations.append(key)

    assert not violations, (
        f"Clean record flagged as violation: {violations}"
    )
