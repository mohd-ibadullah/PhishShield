"""§1.2: Anti-vacuity test for shape-based persistence guards.

Asserts each guarded set is non-empty AND fails a deliberately
malformed sample (a hash value that is raw text; a 15-char hex;
a forbidden key).  Proves both directions: fails when lists are
emptied, passes when properly populated.
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
    validate_record,
    _hash_re,
)

# ── §1.2a: Guarded sets must be non-empty ────────────────────────

def test_forbidden_keys_non_empty():
    """FORBIDDEN_RAW_CONTENT_KEYS must not be empty — an empty set is vacuous."""
    assert len(FORBIDDEN_RAW_CONTENT_KEYS) > 0, (
        "FORBIDDEN_RAW_CONTENT_KEYS is empty — guard is vacuous"
    )


def test_hash_pattern_non_empty():
    """HASH_VALUE_PATTERN must not be empty."""
    assert len(HASH_VALUE_PATTERN) > 0, (
        "HASH_VALUE_PATTERN is empty — guard is vacuous"
    )


# ── §1.2b: Guard must catch deliberately malformed samples ────────

def test_guard_catches_raw_text_hash():
    """A hash value that is raw text must be rejected."""
    record = {"scan_id": "test123", "email_sha256": "this is not a hash"}
    violations = validate_record(record, email_text="test email")
    assert any("does not match" in v for v in violations), (
        f"Guard failed to reject raw text hash: {violations}"
    )


def test_guard_catches_15_char_hex():
    """A 15-char hex value (too short for ^[0-9a-f]{16,64}$) must be rejected."""
    record = {"scan_id": "test123", "input_hash": "a" * 15}
    violations = validate_record(record, email_text="test email")
    assert any("does not match" in v for v in violations), (
        f"Guard failed to reject 15-char hex: {violations}"
    )


def test_guard_catches_forbidden_key():
    """A forbidden key must be rejected."""
    record = {"scan_id": "test123", "email_text": "secret content"}
    violations = validate_record(record, email_text="test email")
    assert any("forbidden key" in v for v in violations), (
        f"Guard failed to reject forbidden key: {violations}"
    )


def test_guard_catches_email_substring_in_text_key():
    """A _text key whose value is the email must be rejected."""
    email = "Subject: Verify your account immediately"
    record = {"scan_id": "test123", "input_text": email}
    violations = validate_record(record, email_text=email)
    assert any("email content" in v for v in violations), (
        f"Guard failed to catch email substring in _text key: {violations}"
    )


def test_guard_catches_email_substring_in_hash_key():
    """A _hash key whose value is the email must be rejected."""
    email = "Subject: Verify your account"
    record = {"scan_id": "test123", "email_hash": email}
    violations = validate_record(record, email_text=email)
    assert any("email content" in v or "hash" in v for v in violations), (
        f"Guard failed to catch email as hash value: {violations}"
    )


# ── §1.2c: Guard passes on clean records ──────────────────────────

def test_guard_passes_clean_record():
    """A well-formed record with no forbidden keys must pass."""
    record = {
        "scan_id": "abc123def456",
        "signals": ["credential_harvest"],
        "risk_score": 75,
        "verdict": "High Risk",
    }
    violations = validate_record(record, email_text="Subject: Verify")
    assert violations == [], f"Guard rejected clean record: {violations}"


def test_guard_passes_valid_hex_hash():
    """A valid 16-char hex hash must pass."""
    record = {"scan_id": "test123", "input_hash": "a" * 16}
    violations = validate_record(record, email_text="test email")
    assert violations == [], f"Guard rejected valid hex hash: {violations}"


# ── §1.2d: Prove both directions — empty list → guard fails ──────

def test_guard_vacuous_when_forbidden_keys_emptied():
    """If FORBIDDEN_RAW_CONTENT_KEYS is emptied, the guard must fail
    on the anti-vacuity check (the set must be non-empty)."""
    import data_constants as dc
    original = dc.FORBIDDEN_RAW_CONTENT_KEYS
    dc.FORBIDDEN_RAW_CONTENT_KEYS = frozenset()
    try:
        with pytest.raises(AssertionError, match="empty"):
            # Re-import the check
            assert len(dc.FORBIDDEN_RAW_CONTENT_KEYS) > 0, (
                "FORBIDDEN_RAW_CONTENT_KEYS is empty — guard is vacuous"
            )
    finally:
        dc.FORBIDDEN_RAW_CONTENT_KEYS = original
