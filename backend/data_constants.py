"""Shared constants for data-minimisation guards.

Single source of truth: both the writer (main.py) and the tests import
from here.  No second copy.  Drift between two lists is how this class
of defect happened three times.
"""
from __future__ import annotations

# Keys that are ALLOWED in persisted stores.  Values must be exactly
# 16 lowercase hex characters (HMAC-SHA256 prefix).
# input_hash was removed: scan_id serves correlation, no external consumer.
PERSISTABLE_HASH_KEYS: frozenset[str] = frozenset()

# Keys that must NEVER appear in any persisted store.  These contain
# email-derived free text or client-identifying information.
FORBIDDEN_RAW_CONTENT_KEYS: frozenset[str] = frozenset({
    "email_text",
    "input_preview",
    "headers",
    "client_ip",
})

# Regex for validating PERSISTABLE_HASH_KEYS values.
HASH_VALUE_PATTERN: str = "^[0-9a-f]{16}$"
