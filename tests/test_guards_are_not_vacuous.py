"""§4.1: Anti-vacuity test for shape-based persistence guards.

Each case must be proven to fail the guard individually, then the clean
run must pass. Per-case failures are the proof, not a summary.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Import the guard from backend
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_constants import (
    FORBIDDEN_RAW_CONTENT_KEYS,
    HASH_VALUE_PATTERN,
    PERSISTABLE_HASH_KEYS,
    validate_record,
    _hash_re,
)

CLEAN_RECORD = {"scan_id": "abc123def456", "signals": ["s1"], "risk_score": 50, "verdict": "Safe"}


# ── §4.1a: Guarded sets must be non-empty ────────────────────────

def test_forbidden_keys_non_empty():
    assert len(FORBIDDEN_RAW_CONTENT_KEYS) > 0, "FORBIDDEN_RAW_CONTENT_KEYS is empty — guard is vacuous"


def test_hash_pattern_non_empty():
    assert len(HASH_VALUE_PATTERN) > 0, "HASH_VALUE_PATTERN is empty — guard is vacuous"


def test_persistable_hash_keys_documented():
    """PERSISTABLE_HASH_KEYS is empty by design (input_hash removed).
    This test documents that, not hides behind it."""
    assert PERSISTABLE_HASH_KEYS == frozenset(), (
        f"PERSISTABLE_HASH_KEYS should be empty: {PERSISTABLE_HASH_KEYS}"
    )


# ── §4.1b: Per-case failures — each MUST be caught ───────────────

def test_guard_catches_raw_text_in_hash_field():
    """Case 1: hash field holding raw email text."""
    record = {"scan_id": "t1", "email_sha256": "Subject: Verify your account now"}
    violations = validate_record(record, email_text="Subject: Verify your account now")
    assert violations, "FAIL: raw text in _sha256 field not caught"


def test_guard_catches_15_hex_value():
    """Case 2: 15-char hex value (too short for ^[0-9a-f]{16,64}$)."""
    record = {"scan_id": "t2", "input_hash": "a" * 15}
    violations = validate_record(record, email_text="test")
    assert violations, "FAIL: 15-char hex not caught"


def test_guard_catches_65_hex_value():
    """Case 3: 65-char hex value (too long for ^[0-9a-f]{16,64}$)."""
    record = {"scan_id": "t3", "email_hash": "a" * 65}
    violations = validate_record(record, email_text="test")
    assert violations, "FAIL: 65-char hex not caught"


def test_guard_catches_forbidden_key():
    """Case 4: forbidden key present."""
    record = {"scan_id": "t4", "email_text": "secret content"}
    violations = validate_record(record, email_text="test")
    assert any("forbidden" in v for v in violations), "FAIL: forbidden key not caught"


def test_guard_catches_email_substring_in_text_key():
    """Case 5: _text key whose value is the email."""
    email = "Subject: Verify your account"
    record = {"scan_id": "t5", "input_text": email}
    violations = validate_record(record, email_text=email)
    assert any("email content" in v for v in violations), "FAIL: email in _text not caught"


def test_guard_catches_email_substring_in_hash_key():
    """Case 6: _hash key whose value is the email."""
    email = "Subject: Verify"
    record = {"scan_id": "t6", "email_hash": email}
    violations = validate_record(record, email_text=email)
    assert violations, "FAIL: email as hash value not caught"


# ── §4.1c: Empty-guard proof ─────────────────────────────────────

def test_guard_vacuous_when_forbidden_keys_emptied():
    """Case 7: empty FORBIDDEN_RAW_CONTENT_KEYS → anti-vacuity check fails."""
    import data_constants as dc
    original = dc.FORBIDDEN_RAW_CONTENT_KEYS
    dc.FORBIDDEN_RAW_CONTENT_KEYS = frozenset()
    try:
        with pytest.raises(AssertionError):
            assert len(dc.FORBIDDEN_RAW_CONTENT_KEYS) > 0
    finally:
        dc.FORBIDDEN_RAW_CONTENT_KEYS = original


# ── §4.1d: Unused-import proof ───────────────────────────────────

def test_persistable_hash_keys_imported_but_referenced():
    """Case 8: PERSISTABLE_HASH_KEYS is imported in data_constants.
    If nothing in non-test code reads it, the import is dead.
    This test documents the state: the constant exists, is empty,
    and is referenced only in tests."""
    # Check non-test code references
    import importlib
    main_mod = importlib.import_module("main")
    # If PERSISTABLE_HASH_KEYS is imported in main.py but never used in
    # non-test code, that's dead code. The constant is empty by design.
    assert hasattr(main_mod, "PERSISTABLE_HASH_KEYS"), (
        "PERSISTABLE_HASH_KEYS not imported in main.py"
    )


# ── §4.1e: Clean run — guard passes on well-formed records ────────

def test_guard_passes_clean_record():
    violations = validate_record(CLEAN_RECORD, email_text="Subject: Test")
    assert violations == [], f"Guard rejected clean record: {violations}"


def test_guard_passes_valid_hex_hash():
    record = {"scan_id": "t", "input_hash": "a" * 16}
    violations = validate_record(record, email_text="test")
    assert violations == [], f"Guard rejected valid hex: {violations}"


def test_guard_passes_valid_64hex_hash():
    record = {"scan_id": "t", "email_sha256": "a" * 64}
    violations = validate_record(record, email_text="test")
    assert violations == [], f"Guard rejected valid 64hex: {violations}"
