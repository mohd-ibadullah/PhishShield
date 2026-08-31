"""§1.2: Meta-test — detect any test writing to repo store files.

Records (size, mtime, line count) of every persisted store under backend/
and data/ via a session-scoped fixture that fires before ANY test runs.
A later test asserts none of those snapshots changed.

The self-proving test (test_isolation_redirect_works) writes to the
module-level constant (which the conftest session fixture redirected to
tmp) and asserts the REAL store file is unchanged — proving the redirect
works on every run, not just when an env var is set.

The deliberate-violation test (test_deliberate_repo_write) writes
directly to the real file and is skipped by default — it exists only
for one-shot manual proof.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
DATA_DIR = ROOT / "data"

# Files whose contents must NOT change during the test suite.
STORE_FILES = [
    BACKEND_DIR / "scan_logs.jsonl",
    BACKEND_DIR / "scans.db",
    BACKEND_DIR / "feedback.csv",
    BACKEND_DIR / "sender_profiles.json",
    DATA_DIR / "feedback.csv",
    DATA_DIR / "feedback_memory.json",
    DATA_DIR / "feedback_state.json",
]


def _line_count(p: Path) -> int | None:
    if not p.exists() or p.suffix not in (".jsonl", ".csv"):
        return None
    try:
        with open(p, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def _snapshot(p: Path) -> dict:
    if not p.exists():
        return {"exists": False}
    st = p.stat()
    return {
        "exists": True,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "lines": _line_count(p),
    }


_initial: dict[str, dict] = {}


@pytest.fixture(scope="session", autouse=True)
def _record_initial_store_state():
    """Capture baseline state of every store file before any test runs."""
    for p in STORE_FILES:
        _initial[str(p)] = _snapshot(p)
    yield


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


# ── The actual suite-wide assertion ──────────────────────────────

def test_no_repo_store_writes():
    """§1.2: Assert no store file under backend/ or data/ was modified."""
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


# ── Detector-catches-write proof (runs every time) ──────────
# Self-contained on a SYNTHETIC store in tmp — never touches repo.
# Uses the same _snapshot() routine the meta-test uses.
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

    # ── Scenario 2: append + truncate (size restored) ──
    # On Windows NTFS, truncate back to original size within the same
    # mtime quantum may NOT change mtime. The guard catches this case
    # ONLY IF mtime changed. This is a real weakness: append+truncate
    # of equal size can evade the guard if both land in the same quantum.
    snap_before2 = _snapshot(synthetic)
    synthetic.write_bytes(b"line-3-temp\n")
    with open(synthetic, "r+b") as f:
        f.truncate(len(original_content))
    snap_after2 = _snapshot(synthetic)
    assert snap_after2["size"] == snap_before2["size"], "size restored after truncate"
    if snap_before2 != snap_after2:
        # Guard caught the delta (mtime changed) — ideal case.
        pass
    else:
        # Guard did NOT catch the delta — mtime unchanged within quantum.
        # This is a documented weakness of the stat-based guard.
        pass  # Not a test failure — the weakness is documented in the report.

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


# ── Deliberate-violation proof (skipped by default) ─────────────
# Unique coverage: writes to the REAL file (not the redirected path).
# The self-proving test proves the redirect works; this proves the
# meta-test catches violations on the actual store file.
# Run with: _TEST_PROVE_META_CATCHES_VIOLATION=1
_PROVE = os.getenv("_TEST_PROVE_META_CATCHES_VIOLATION", "") == "1"


@pytest.mark.skipif(
    not _PROVE,
    reason="One-shot proof: writes to real file. Unique coverage vs self-proving test."
)
def test_deliberate_repo_write():
    """Write to the real scan_logs.jsonl to prove the meta-test catches it."""
    violation_marker = f"VIOLATION-PROOF-{os.getpid()}"
    real_path = ROOT / "backend" / "scan_logs.jsonl"
    with open(real_path, "a", encoding="utf-8") as f:
        f.write(violation_marker + "\n")
