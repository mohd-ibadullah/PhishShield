"""§6.2: Ambient-state check — tests must pass regardless of env vars.

PORT=0 and unset PHISHSHIELD_PREVIEW_HMAC_KEY should not break tests.
This is the class of bug that recurred three times today.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _run_suite(env_overrides: dict[str, str | None]) -> tuple[int, str]:
    """Run the test suite with specific env overrides, return (exit_code, output)."""
    env = os.environ.copy()
    for k, v in env_overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider",
         "--tb=no", "-x"],
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
    )
    return result.returncode, result.stdout + result.stderr


def test_suite_passes_with_port_zero():
    """PORT=0 must not break the test suite."""
    code, output = _run_suite({"PORT": "0"})
    # Extract summary line
    lines = [l for l in output.splitlines() if "passed" in l or "failed" in l]
    summary = lines[-1] if lines else output[-200:]
    assert code == 0, f"Suite failed with PORT=0: {summary}"


def test_suite_passes_with_port_unset():
    """Unset PORT must not break the test suite."""
    code, output = _run_suite({"PORT": None})
    lines = [l for l in output.splitlines() if "passed" in l or "failed" in l]
    summary = lines[-1] if lines else output[-200:]
    assert code == 0, f"Suite failed with PORT unset: {summary}"


def test_hmac_key_required():
    """Unset PHISHSHIELD_PREVIEW_HMAC_KEY must cause documented refusal at startup,
    not a silent fallback."""
    # The app should refuse to start without the HMAC key.
    # We test this by importing main.py without the key set.
    import importlib
    env_backup = os.environ.get("PHISHSHIELD_PREVIEW_HMAC_KEY")
    try:
        os.environ.pop("PHISHSHIELD_PREVIEW_HMAC_KEY", None)
        # Force re-import
        if "main" in sys.modules:
            del sys.modules["main"]
        # The import should work (lazy key loading), but _get_preview_hmac_key
        # should raise when called without the key.
        mod = importlib.import_module("main")
        with pytest.raises(RuntimeError, match="PHISHSHIELD_PREVIEW_HMAC_KEY"):
            mod._get_preview_hmac_key()
    finally:
        if env_backup is not None:
            os.environ["PHISHSHIELD_PREVIEW_HMAC_KEY"] = env_backup
        elif "PHISHSHIELD_PREVIEW_HMAC_KEY" in os.environ:
            del os.environ["PHISHSHIELD_PREVIEW_HMAC_KEY"]
