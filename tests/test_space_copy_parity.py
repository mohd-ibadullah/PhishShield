"""Guarded-behaviour parity between backend/ and the deployed Space copy.

phishshield-backend-space/ is the source of the public Hugging Face Space.
These checks extract the security-guard function blocks from both copies and
fail when they diverge, so a fix applied to only one copy cannot slip through.

Pre-existing drift recorded 2026-08-30 (before the W2 fixes; do not mistake
this drift for a later edit): backend/main.py 8485 lines vs
phishshield-backend-space/main.py 8421 lines (~64-line delta, the space copy
predating the health/metrics/metadata hardening commits).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_MAIN = ROOT / "backend" / "main.py"
SPACE_MAIN = ROOT / "phishshield-backend-space" / "main.py"

GUARDED_BLOCKS = [
    "def _validate_internal_access(",
    "def validate_internal_key_configuration(",
]

# D2: Additional guarded patterns (string search, not function-block extraction)
GUARDED_PATTERNS = {
    # No hardcoded accuracy/f1 defaults — must use _format_health_metric from metadata
    "no_indicbert_health_constants": (
        lambda src: "INDICBERT_HEALTH_ACCURACY" not in src and "INDICBERT_HEALTH_F1" not in src,
        "Space copy must not contain hardcoded INDICBERT_HEALTH_ACCURACY/F1 constants"
    ),
    # RETRAINING_METADATA_PATH must exist
    "retraining_metadata_path": (
        lambda src: "RETRAINING_METADATA_PATH" in src,
        "Space copy must define RETRAINING_METADATA_PATH"
    ),
    # Coercive threat regex must exist in is_otp_safety_notice
    "coercive_threat_regex": (
        lambda src: "is_coercive_threat" in src,
        "Space copy must contain coercive threat regex in is_otp_safety_notice"
    ),
    # model_improving must default to False
    "model_improving_default_false": (
        lambda src: src.count('"model_improving": True') == 0 or src.count('"model_improving": False') > 0,
        "Space copy model_improving must default to False"
    ),
}


def _extract_block(source: str, signature: str) -> str | None:
    """Return the full function block starting at signature, or None if absent."""
    start = source.find(signature)
    if start == -1:
        return None
    rest = source[start:]
    match = re.search(r"\n(?:def |@|class )", rest[len(signature):])
    end = len(signature) + match.start() if match else len(rest)
    return rest[:end].strip()


def test_space_copy_exists() -> None:
    assert SPACE_MAIN.exists(), "phishshield-backend-space/main.py missing (embedded repo not checked out?)"


def test_guarded_blocks_match_space_copy() -> None:
    backend_source = BACKEND_MAIN.read_text(encoding="utf-8")
    space_source = SPACE_MAIN.read_text(encoding="utf-8")
    for signature in GUARDED_BLOCKS:
        backend_block = _extract_block(backend_source, signature)
        space_block = _extract_block(space_source, signature)
        assert backend_block is not None, f"{signature} missing from backend/main.py"
        assert space_block is not None, f"{signature} missing from phishshield-backend-space/main.py"
        assert backend_block == space_block, f"{signature} diverges between backend/ and the Space copy"


def test_guarded_patterns_match_space_copy() -> None:
    """D2: Verify additional security patterns are present in the Space copy."""
    space_source = SPACE_MAIN.read_text(encoding="utf-8")
    for name, (check, msg) in GUARDED_PATTERNS.items():
        assert check(space_source), f"Parity guard '{name}' failed: {msg}"
