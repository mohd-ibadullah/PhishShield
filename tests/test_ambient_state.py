"""§6.2: Ambient-state check — tests must pass regardless of env vars.

PORT=0 and unset PHISHSHIELD_PREVIEW_HMAC_KEY must not break the test suite.

Isolation contract for the child pytest process:
- runs a bounded representative subset (one security, one minimisation, one
  API test) — never the whole suite;
- inherits PHISHSHIELD_STORE_DIR, the single store-redirect knob that both
  parent and child resolve store paths from (set by conftest before main.py
  is imported), so the child never touches the repo working tree;
- child args pin -p no:randomly for deterministic ordering;
- timeout is measured mean x 3 (floored), not a guess; on failure or timeout
  the child's last 30 stderr lines are printed.

The sys.modules eviction in test_hmac_key_required is wrapped in a guard
fixture that restores the original module object on teardown; the follow-up
test asserts backend.main is the pre-test object after the ambient tests.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Representative subset: one security, one minimisation, one API test.
_REPRESENTATIVE_TESTS = [
    "tests/test_security_basics.py",
    "tests/test_data_minimization.py",
    "tests/test_endpoint_gating.py",
]

# Pre-test object: conftest imported main before this module was collected.
_ORIGINAL_MAIN = sys.modules.get("main")

_STORE_REDIRECT_ENV = "PHISHSHIELD_STORE_DIR"

# First child run uses this generous ceiling; subsequent runs use 3x the
# measured mean duration (floored at 60s).  Mean is over completed runs in
# this session only — no invented constant.
_DEFAULT_TIMEOUT_S = 180.0
_TIMEOUT_FLOOR_S = 60.0
_durations: list[float] = []


def _last_stderr_lines(stderr: str | bytes | None, n: int = 30) -> str:
    if not stderr:
        return "<no stderr captured>"
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    return "\n".join(stderr.splitlines()[-n:])


def _run_subset(env_overrides: dict[str, str | None]) -> tuple[int, str]:
    """Run representative tests with specific env overrides, return (exit_code, output)."""
    env = os.environ.copy()
    for k, v in env_overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v

    # The child MUST inherit the store-redirect knob; if conftest did not set
    # it, fail here rather than spawn a child that writes the repo stores.
    redirect = env.get(_STORE_REDIRECT_ENV)
    assert redirect, (
        f"{_STORE_REDIRECT_ENV} not set in parent env — conftest must set it "
        "before spawning child pytest processes"
    )
    env[_STORE_REDIRECT_ENV] = redirect

    if _durations:
        mean = sum(_durations) / len(_durations)
        timeout = max(_TIMEOUT_FLOOR_S, round(3 * mean, 1))
    else:
        timeout = _DEFAULT_TIMEOUT_S

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *_REPRESENTATIVE_TESTS,
             "-q", "-p", "no:randomly", "-p", "no:cacheprovider", "--tb=no", "-x"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"child pytest timed out after {timeout}s "
            f"(measured mean x 3 = {timeout}; mean over {_durations}). "
            f"Child's last 30 stderr lines:\n{_last_stderr_lines(exc.stderr)}",
            pytrace=False,
        )
    _durations.append(time.monotonic() - t0)

    return result.returncode, result.stdout + (result.stderr or "")


def test_suite_passes_with_port_zero():
    """PORT=0 must not break the test suite."""
    code, output = _run_subset({"PORT": "0"})
    lines = [l for l in output.splitlines() if "passed" in l or "failed" in l]
    summary = lines[-1] if lines else output[-200:]
    assert code == 0, (
        f"Suite failed with PORT=0: {summary}\n"
        f"Child's last 30 stderr lines:\n{_last_stderr_lines(output)}"
    )


def test_suite_passes_with_port_unset():
    """Unset PORT must not break the test suite."""
    code, output = _run_subset({"PORT": None})
    lines = [l for l in output.splitlines() if "passed" in l or "failed" in l]
    summary = lines[-1] if lines else output[-200:]
    assert code == 0, (
        f"Suite failed with PORT unset: {summary}\n"
        f"Child's last 30 stderr lines:\n{_last_stderr_lines(output)}"
    )


@pytest.fixture
def _restore_evicted_main(sys_modules_guard):
    """Restore the original main module object after the eviction test.

    Without this, the re-imported module replaces the conftest-imported one
    and every later in-process store write escapes the redirect.
    """
    sys_modules_guard("main")
    yield


@ pytest.mark.usefixtures("_restore_evicted_main")
def test_hmac_key_required():
    """Unset PHISHSHIELD_PREVIEW_HMAC_KEY must cause documented refusal at startup,
    not a silent fallback.

    Tests the function directly: clears the cached key, unsets the env var,
    calls the function, then restores both. Does NOT re-import the module
    (load_dotenv would restore the key from .env on re-import).
    """
    import importlib
    import backend.main as backend_main_module
    env_backup = os.environ.get("PHISHSHIELD_PREVIEW_HMAC_KEY")
    cached_backup = backend_main_module._PREVIEW_HMAC_KEY
    try:
        os.environ.pop("PHISHSHIELD_PREVIEW_HMAC_KEY", None)
        backend_main_module._PREVIEW_HMAC_KEY = None
        with pytest.raises(RuntimeError, match="PHISHSHIELD_PREVIEW_HMAC_KEY"):
            backend_main_module._get_preview_hmac_key()
    finally:
        backend_main_module._PREVIEW_HMAC_KEY = cached_backup
        if env_backup is not None:
            os.environ["PHISHSHIELD_PREVIEW_HMAC_KEY"] = env_backup
        elif "PHISHSHIELD_PREVIEW_HMAC_KEY" in os.environ:
            del os.environ["PHISHSHIELD_PREVIEW_HMAC_KEY"]


def test_main_module_restored_after_eviction():
    """After the ambient tests, backend.main must be the pre-test object —
    the eviction test's guard fixture must have restored it."""
    assert sys.modules.get("main") is _ORIGINAL_MAIN, (
        "sys.modules['main'] is not the pre-test object: an eviction without "
        "restore leaked a re-imported module into the session"
    )
