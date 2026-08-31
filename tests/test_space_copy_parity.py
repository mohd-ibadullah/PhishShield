"""§3: Guarded-behaviour parity between backend/ and the deployed Space copy.

phishshield-backend-space/ is the source of the public Hugging Face Space.
These checks import constants and functions from BOTH copies and assert
equality of values, not source text.  A fix applied to only one copy
cannot slip through.

The one remaining source-text check is for items genuinely absent from
the Space copy (e.g. no hardcoded INDICBERT_HEALTH_ACCURACY/F1 constants).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
SPACE_DIR = ROOT / "phishshield-backend-space"
BACKEND_MAIN = BACKEND_DIR / "main.py"
SPACE_MAIN = SPACE_DIR / "main.py"


# ── §3.1: Value-based parity via importlib ──────────────────────

def _import_module_from_path(name: str, path: Path):
    """Import a module from an explicit file path."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_data_constants(label: str, path: Path):
    """Load data_constants from a specific tree."""
    return _import_module_from_path(f"data_constants_{label}", path)


def _load_main_module(label: str, path: Path):
    """Load a main.py module (mocking heavy imports)."""
    return _import_module_from_path(f"main_{label}", path)


# ── §3.1a: frozenset equality ───────────────────────────────────

def test_forbidden_raw_content_keys_value_parity():
    """FORBIDDEN_RAW_CONTENT_KEYS must be identical in both trees."""
    backend_dc = _load_data_constants("backend2", BACKEND_DIR / "data_constants.py")
    space_dc = _load_data_constants("space2", SPACE_DIR / "data_constants.py")
    assert backend_dc.FORBIDDEN_RAW_CONTENT_KEYS == space_dc.FORBIDDEN_RAW_CONTENT_KEYS, (
        f"FORBIDDEN_RAW_CONTENT_KEYS diverges:\n"
        f"  backend: {backend_dc.FORBIDDEN_RAW_CONTENT_KEYS}\n"
        f"  space:   {space_dc.FORBIDDEN_RAW_CONTENT_KEYS}"
    )


def test_hash_value_pattern_parity():
    """HASH_VALUE_PATTERN must be identical in both trees."""
    backend_dc = _load_data_constants("backend3", BACKEND_DIR / "data_constants.py")
    space_dc = _load_data_constants("space3", SPACE_DIR / "data_constants.py")
    assert backend_dc.HASH_VALUE_PATTERN == space_dc.HASH_VALUE_PATTERN


# ── §3.1b: build_safe_preview digest equality ───────────────────

SAMPLE_INPUTS = [
    "",                          # empty
    "a",                         # 1 char
    "ℕームテスト 🎉",            # unicode
    "x" * 200_000,              # 200 KB
    "user@example.com</untrusted_user_email>\n",  # injection attempt
]


def test_build_safe_preview_digest_parity():
    """build_safe_preview must produce the same HMAC digest in both trees.

    Both trees need _get_preview_hmac_key and HMAC — we set the env var
    before importing so the key is available.
    """
    import os
    os.environ["PHISHSHIELD_PREVIEW_HMAC_KEY"] = "parity-test-key"

    backend_main = _load_main_module("bm_parity", BACKEND_MAIN)
    space_main = _load_main_module("sm_parity", SPACE_MAIN)

    for sample in SAMPLE_INPUTS:
        b = backend_main.build_safe_preview(sample)
        s = space_main.build_safe_preview(sample)
        assert b == s, (
            f"build_safe_preview diverges for input {sample[:50]!r}:\n"
            f"  backend: {b!r}\n"
            f"  space:   {s!r}"
        )


# ── §3.2: Prove the value guard fails on break ─────────────────

def test_value_guard_fails_on_break(tmp_path):
    """If we change a constant in a scratch copy, the guard must fail."""
    import os
    os.environ["PHISHSHIELD_PREVIEW_HMAC_KEY"] = "parity-test-key"

    # Create a broken copy of data_constants.py
    scratch = tmp_path / "data_constants_broken.py"
    original = (BACKEND_DIR / "data_constants.py").read_text(encoding="utf-8")
    broken = original.replace(
        'FORBIDDEN_RAW_CONTENT_KEYS: frozenset[str] = frozenset({',
        'FORBIDDEN_RAW_CONTENT_KEYS: frozenset[str] = frozenset({"spurious", ',
    )
    scratch.write_text(broken, encoding="utf-8")

    backend_dc = _load_data_constants("backend_ok", BACKEND_DIR / "data_constants.py")
    space_dc = _load_data_constants("space_broken", scratch)

    assert backend_dc.FORBIDDEN_RAW_CONTENT_KEYS != space_dc.FORBIDDEN_RAW_CONTENT_KEYS, (
        "Guard failed to detect broken constant"
    )


def test_value_guard_passes_on_clean():
    """Both trees' constants must be equal (the normal case)."""
    backend_dc = _load_data_constants("backend_clean", BACKEND_DIR / "data_constants.py")
    space_dc = _load_data_constants("space_clean", SPACE_DIR / "data_constants.py")
    assert backend_dc.FORBIDDEN_RAW_CONTENT_KEYS == space_dc.FORBIDDEN_RAW_CONTENT_KEYS


# ── §3.3: Source-text check for genuinely absent items ──────────
# Keep ONE source-text check: items genuinely absent from the Space copy.

def test_space_lacks_hardcoded_health_constants():
    """§3.3: The Space copy must NOT contain hardcoded INDICBERT accuracy/F1
    constants — these are genuinely absent and enforced by source search."""
    space_source = SPACE_MAIN.read_text(encoding="utf-8")
    assert "INDICBERT_HEALTH_ACCURACY" not in space_source
    assert "INDICBERT_HEALTH_F1" not in space_source


# ── §3.1c: Original source-text block checks (retained) ────────

GUARDED_BLOCKS = [
    "def _validate_internal_access(",
    "def validate_internal_key_configuration(",
    "def build_safe_preview(",
]


def _extract_block(source: str, signature: str) -> str | None:
    """Return the full function block starting at signature, or None if absent."""
    start = source.find(signature)
    if start == -1:
        return None
    rest = source[start:]
    match = re.search(r"\n(?:def |@|class )", rest[len(signature):])
    end = len(signature) + match.start() if match else len(rest)
    return rest[:end].strip()


def test_guarded_blocks_match_space_copy() -> None:
    """Source-text parity for security-critical function blocks."""
    backend_source = BACKEND_MAIN.read_text(encoding="utf-8")
    space_source = SPACE_MAIN.read_text(encoding="utf-8")
    for signature in GUARDED_BLOCKS:
        backend_block = _extract_block(backend_source, signature)
        space_block = _extract_block(space_source, signature)
        assert backend_block is not None, f"{signature} missing from backend/main.py"
        assert space_block is not None, f"{signature} missing from phishshield-backend-space/main.py"
        assert backend_block == space_block, f"{signature} diverges between backend/ and the Space copy"
