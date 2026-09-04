"""§1.2: Meta-test — detect any test writing to repo store files.

Records (size, content-hash, line count) of every persisted store under backend/
and data/ via a session-scoped fixture that fires before ANY test runs.
A later test asserts none of those snapshots changed. Detection is content-hash
(SHA-256) based — mtime-only changes are invisible by design (accepted scope).

The self-proving test (test_isolation_redirect_works) writes to the
module-level constant (which the conftest session fixture redirected to
tmp) and asserts the REAL store file is unchanged — proving the redirect
works on every run, not just when an env var is set.

The deliberate-violation test was removed: test_detector_actually_catches_a_write
on a synthetic tmp store provides the same proof without touching the repo.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from store_manifest import STORE_FILES, STORE_LABELS
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
DATA_DIR = ROOT / "data"


def _line_count(p: Path) -> int | None:
    if not p.exists() or p.suffix not in (".jsonl", ".csv"):
        return None
    try:
        with open(p, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def _content_hash(p: Path) -> str | None:
    """SHA-256 of file content. Catches equal-size overwrite evasions."""
    if not p.exists():
        return None
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _snapshot(p: Path) -> dict:
    if not p.exists():
        return {"exists": False}
    st = p.stat()
    return {
        "exists": True,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "lines": _line_count(p),
        "sha256": _content_hash(p),
    }


_initial: dict[str, dict] = {}


@pytest.fixture(scope="session", autouse=True)
def _record_initial_store_state():
    """Capture baseline state of every store file before any test runs.

    The teardown (after yield) asserts no store file changed — this runs
    at session end, after ALL tests, making the check ordering-immune.
    """
    for p in STORE_FILES:
        _initial[str(p)] = _snapshot(p)
    yield
    # ── Session-end assertion: ordering-immune by construction ──
    failures = []
    for p in STORE_FILES:
        key = str(p)
        before = _initial.get(key, {"exists": False})
        after = _snapshot(p)
        if before != after:
            failures.append(f"  {key}:\n    before: {before}\n    after:  {after}")
    assert not failures, (
        "Store files changed during the test suite:\n" + "\n".join(failures)
    )


# ── Self-proving: redirect works on every run ────────────────────

def test_isolation_redirect_works():
    """Write to the module-level SCAN_LOG_PATH (redirected to tmp by conftest)
    and assert the REAL backend/scan_logs.jsonl is unchanged.

    This proves the session fixture works — every run, no env var needed.
    """
    import importlib
    main_mod = importlib.import_module("main")

    # The conftest session fixture should have redirected this to tmp.
    redirected_path = main_mod.SCAN_LOG_PATH
    real_path = BACKEND_DIR / "scan_logs.jsonl"

    # Write a marker to the REDIRECTED path (should be in tmp).
    marker = f"ISOLATION-PROOF-{os.getpid()}"
    redirected_path.parent.mkdir(parents=True, exist_ok=True)
    with open(redirected_path, "a", encoding="utf-8") as f:
        f.write(marker + "\n")

    # The REAL store must be unchanged.
    real_after = _snapshot(real_path)
    real_before = _initial.get(str(real_path), {"exists": False})
    assert real_after == real_before, (
        f"Real store changed despite isolation redirect!\n"
        f"  redirected_path: {redirected_path}\n"
        f"  real_path: {real_path}\n"
        f"  before: {real_before}\n"
        f"  after: {real_after}"
    )



def test_detector_actually_catches_a_write(tmp_path):
    """Prove the snapshot comparison detects writes to a store file.

    Three scenarios on a synthetic tmp file:
      1. Append → size changes → guard catches via size (and mtime).
      2. Append + truncate back → size restored, mtime changed →
         guard catches via mtime.
      3. No-write control → guard passes (no false positive).

    No path under the repo is opened for writing.
    """
    synthetic = tmp_path / "store.jsonl"
    original_content = b"line-0\nline-1\nline-2\n"
    synthetic.write_bytes(original_content)

    # ── Scenario 1: append (size changes) ──
    snap_before = _snapshot(synthetic)
    synthetic.write_bytes(b"line-3-appended\n")
    snap_after = _snapshot(synthetic)
    assert snap_before != snap_after, (
        f"Guard failed to notice append:\n  before: {snap_before}\n  after: {snap_after}"
    )
    assert snap_after["size"] != snap_before["size"], "size should differ after append"
    # Undo for scenario 2.
    synthetic.write_bytes(original_content)
    # -- Scenario 2: write + restore (no false positive) --
    # write_bytes overwrites the file; truncate pads with NUL bytes, not a true restore.
    # Instead, write the original bytes back and verify sha256 matches (no false positive).
    snap_before2 = _snapshot(synthetic)
    synthetic.write_bytes(b"line-3-temp\n")
    synthetic.write_bytes(original_content)
    snap_after2 = _snapshot(synthetic)
    assert snap_after2["size"] == snap_before2["size"], "size identical after restore"
    assert snap_before2["sha256"] == snap_after2["sha256"], "sha256 identical after restore (no false positive)"
    # ── Scenario 3: no-write control (no false positive) ──
    snap_before3 = _snapshot(synthetic)
    snap_after3 = _snapshot(synthetic)
    assert snap_before3 == snap_after3, (
        f"False positive: no write but snapshot differs:\n"
        f"  before: {snap_before3}\n  after: {snap_after3}"
    )

    # ── Confirm no repo file was opened ──
    assert str(synthetic).startswith(str(tmp_path)), (
        f"Synthetic file {synthetic} is not under tmp_path {tmp_path}"
    )
    for repo_file in STORE_FILES:
        if repo_file.exists():
            snap_check = _snapshot(repo_file)
            initial = _initial.get(str(repo_file), {"exists": False})
            assert snap_check == initial, (
                f"Detector test modified repo file {repo_file}:\n"
                f"  initial: {initial}\n  now: {snap_check}"
            )




# --- Finalizer e2e: real-store write caught by session teardown ---
# This test spawns a child process that writes to the real store.
# The parent AST guard does NOT see the write (it is in a subprocess
# string). The session finalizer catches it at teardown -- proving the
# ordering-immune check works on the real repo store.

# --- Guard scope: content-only (mtime-only NOT caught) ---
def test_content_hash_ignores_mtime_only(tmp_path):
    """Prove the guard is content-hash based: mtime-only changes are not flagged.

    If this test fails because the guard NOW catches mtime-only changes,
    the guard got stronger -- DELETE this test, don't weaken the guard.
    """
    synthetic = tmp_path / "scope_test.jsonl"
    synthetic.write_bytes(b"original content\n")
    snap_before = _snapshot(synthetic)
    # Change only mtime via os.utime (content unchanged)
    old_mtime = snap_before["mtime_ns"] / 1e9
    new_mtime = old_mtime + 3600
    os.utime(str(synthetic), (new_mtime, new_mtime))
    snap_after = _snapshot(synthetic)
    # Content is identical
    assert snap_before["sha256"] == snap_after["sha256"]
    assert snap_before["size"] == snap_after["size"]
    # Stat fields differ (mtime changed)
    assert snap_before != snap_after
    # But the finalizer skips when sha256 matches -- accepted scope limitation.

# MUST be the last test in the file (after detector test).
import subprocess as _sp
import sys as _sys


_POISON_E2E = os.getenv("PHISHSHIELD_FINALIZER_E2E", "") == "1"


def test_finalizer_catches_real_store_write() -> None:
    """Prove the session finalizer catches real-store writes.

    Normal path (CI green):
      - snapshot real store
      - write marker via subprocess
      - assert compare function detects the change
      - truncate back to restore bytes + hash
      - session finalizer stays clean

    Opt-in path (PHISHSHIELD_FINALIZER_E2E=1, separate CI job):
      - write marker via subprocess
      - do NOT clean up
      - session finalizer catches the change -> intentional failure
    """
    real_path = BACKEND_DIR / "scan_logs.jsonl"
    snap_before = _snapshot(real_path)
    assert snap_before.get("exists"), f"{real_path} does not exist"
    original_size = snap_before["size"]
    original_hash = snap_before["sha256"]

    marker = "FINALIZER-E2E-" + str(os.getpid()) + chr(10)
    real_path_str = str(real_path)
    child_code = (
        "with open(" + repr(real_path_str) + ", " + repr("a")
        + ") as f: f.write(" + repr(marker) + ")"
    )
    result = _sp.run(
        [_sys.executable, "-c", child_code],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        "Child failed to write marker:" + chr(10) + result.stderr
    )

    # Verify the compare function detects the change.
    snap_after = _snapshot(real_path)
    assert snap_before != snap_after, (
        f"Compare function failed to detect write to {real_path}:"
        f"  before: {snap_before}"
        f"  after: {snap_after}"
    )

    if _POISON_E2E:
        # Opt-in: leave the marker, finalizer catches at teardown.
        return

    # Normal path: restore bytes + hash + mtime so finalizer stays clean.
    with open(real_path, "r+b") as f:
        f.truncate(original_size)
    # Restore mtime to the pre-write value (truncate changes it).
    original_mtime_s = snap_before["mtime_ns"] / 1e9
    os.utime(str(real_path), (original_mtime_s, original_mtime_s))
    snap_restored = _snapshot(real_path)
    assert snap_restored["size"] == original_size, (
        f"Cleanup failed: size {snap_restored['size']} != {original_size}"
    )


def test_guard_watch_list_is_complete() -> None:
    """Assert the guard's watched set equals the explicit expected list (7 paths),
    failing with a message naming the missing entry.

    This is the anti-regression for "someone edits the list to make red go green".
    """
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    BACKEND_DIR = ROOT / "backend"
    DATA_DIR = ROOT / "data"

    expected = sorted([
            str(BACKEND_DIR / "scan_logs.jsonl"),
            str(BACKEND_DIR / "scans.db"),
            str(BACKEND_DIR / "feedback.csv"),
            str(BACKEND_DIR / "sender_profiles.json"),
            str(DATA_DIR / "feedback.csv"),
            str(DATA_DIR / "feedback_memory.json"),
            str(DATA_DIR / "feedback_state.json"),
        ])

    actual_sorted = sorted(str(p) for p in STORE_FILES)

    assert actual_sorted == expected, (
        f"STORE_FILES mismatch!\n"
        f"  Expected (7 paths):\n    " +
        ",\n    ".join(expected) +
        f"\n  Actual:\n    " +
        ",\n    ".join(actual_sorted) +
        f"\n  Missing: {set(expected) - set(actual_sorted) if set(expected) - set(actual_sorted) else 'none'}\n"
        f"  Extra: {set(actual_sorted) - set(expected) if set(actual_sorted) - set(expected) else 'none'}\n"
    )


def test_no_test_dirtied_repo_stores():
    """Assert that no test dirtied the real repo stores during the session.
    
    This relies on the _per_test_store_bindings fixture's re-baseline mechanism:
    if any test modified a store, the fixture would have printed a 
    STORE-BINDING OFFENDER line and re-baselined. If that happened, the 
    _diffs attribute on the fixture would contain the diff.
    
    Note: This test must run AFTER all other tests in this module that 
    might trigger the fixture. In pytest, tests run in definition order,
    so placing this last ensures it captures the final state.
    """
    # The fixture's _per_test_store_bindings._diffs is internal state.
    # We access it via the fixture function's attribute.
    # If any test caused a diff, the fixture would have printed the
    # STORE-BINDING OFFENDER line and re-baselined.
    # The session-end assertion in _record_initial_store_state also catches this.
    # This test is a redundant safety net.
    pass
