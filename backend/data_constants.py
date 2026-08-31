"""Shared constants for data-minimisation guards.

Single source of truth: both the writer (main.py) and the tests import
from here.  No second copy.

Shape-based rules (§1.1): instead of checking specific key names, we
check the VALUES of keys that match certain name patterns.  This makes
the guard resistant to new fields being added that accidentally leak
email content.
"""
from __future__ import annotations

import re
from typing import Any

# ── Keys that must NEVER appear in any persisted store ────────────
# These contain email-derived free text or client-identifying info.
# Checked by name (exact match).
FORBIDDEN_RAW_CONTENT_KEYS: frozenset[str] = frozenset({
    "email_text",
    "input_preview",
    "headers",
    "client_ip",
})

# ── Key-name patterns that trigger value inspection ───────────────
# Any key whose name matches one of these suffixes is inspected:
# its VALUE must not contain email-derived content.
_HASH_KEY_SUFFIXES = ("_hash", "_sha256", "_digest")
_CONTENT_KEY_SUFFIXES = ("_preview", "_text", "_body")

# ── Value format rules ────────────────────────────────────────────
# Keys ending in _hash/_sha256 must match this hex pattern.
HASH_VALUE_PATTERN: str = "^[0-9a-f]{16,64}$"

_hash_re = re.compile(HASH_VALUE_PATTERN)


def _email_is_substring(value: str, email_text: str) -> bool:
    """Check if a stored value is equal to or a substring of the email."""
    if not value or not email_text:
        return False
    v = str(value)
    e = str(email_text)
    # Exact match or first-N-chars match
    if v == e:
        return True
    if len(v) >= 8 and e.startswith(v):
        return True
    if len(v) >= 8 and v in e:
        return True
    return False


def validate_record(
    record: dict[str, Any],
    email_text: str = "",
) -> list[str]:
    """Shape-based validation of a record before persistence.

    Returns a list of violation descriptions (empty = clean).
    Called by append_structured_scan_log before writing.
    """
    violations: list[str] = []

    for key, value in record.items():
        if value is None:
            continue
        val_str = str(value)

        # Rule 1: FORBIDDEN_RAW_CONTENT_KEYS must not be present
        if key in FORBIDDEN_RAW_CONTENT_KEYS:
            violations.append(f"forbidden key '{key}' present")
            continue

        # Rule 2: Hash-value format check
        is_hash_key = any(key.endswith(s) for s in _HASH_KEY_SUFFIXES)
        if is_hash_key and val_str:
            if not _hash_re.match(val_str):
                violations.append(
                    f"key '{key}' value {val_str!r} does not match {HASH_VALUE_PATTERN}"
                )

        # Rule 3: Content leak check — value must not be email substring
        is_content_key = any(key.endswith(s) for s in _CONTENT_KEY_SUFFIXES)
        if is_content_key and email_text and val_str:
            if _email_is_substring(val_str, email_text):
                violations.append(
                    f"key '{key}' value contains email content"
                )

        # Also check hash keys for email substring (belt and suspenders)
        if is_hash_key and email_text and val_str:
            if _email_is_substring(val_str, email_text):
                violations.append(
                    f"key '{key}' hash value is email substring"
                )

    return violations
