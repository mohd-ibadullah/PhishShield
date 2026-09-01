from __future__ import annotations

import importlib
import os
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ── §1.1: Store-isolation via PHISHSHIELD_STORE_DIR ─────────────
# ONE knob, used by both this process and every spawned child: main.py
# resolves ALL persisted-store paths from PHISHSHIELD_STORE_DIR at import
# time, so isolation is driven by config the child inherits — not by an
# in-process fixture patch (which a sys.modules eviction would defeat).
#
# This MUST run before importlib.import_module("main") below.
_STORE_TMP_DIR = Path(tempfile.mkdtemp(prefix="phishshield-stores-"))
os.environ["PHISHSHIELD_STORE_DIR"] = str(_STORE_TMP_DIR)

# ── §1.1: The 7 guarded stores — SINGLE SOURCE OF TRUTH.
# Import from tests/store_manifest.py (the single canonical list).
# All guards, fixtures, and manifest tests share this source.
from store_manifest import STORE_FILES, STORE_LABELS as _STORE_LABELS

os.environ.setdefault("PHISHSHIELD_PREVIEW_HMAC_KEY", "test-hmac-key-for-tests")

# ── HMAC preflight: fail clearly instead of mass-cascading 134 failures ──
def pytest_configure(config):
    """Preflight check: PHISHSHIELD_PREVIEW_HMAC_KEY must be set before collection.

    If the key is absent and no dotenv fills it, the backend refuses to start.
    Without this hook, every test that touches the backend would fail with the
    same RuntimeError — a 134-test cascade that obscures the real cause.
    """
    key = os.environ.get("PHISHSHIELD_PREVIEW_HMAC_KEY")
    if not key:
        try:
            import backend.main as _bm  # noqa: F401
            _key_val = getattr(_bm, "_get_preview_hmac_key", None)
            if _key_val:
                try:
                    _key_val()
                    return  # dotenv or env provided the key
                except RuntimeError:
                    pass  # will fall through to error
        except Exception:
            pass
        config.error(
            "PHISHSHIELD_PREVIEW_HMAC_KEY is not set. "
            "Set it in the environment or .env file before running tests. "
            "This prevents the 134-test RuntimeError cascade seen in L8."
        )

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

# Integration scripts moved to tools/ directory. All 40 test_*.py in tests/ are pytest-valid.

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

backend_main = importlib.import_module("main")
app = backend_main.app

# ── §1.1: Verify every redirected store path is under tmp dir
STORE_PATH_ATTRS = (
    "SCAN_LOG_PATH",
    "SCANS_DB_PATH",
    "FEEDBACK_CSV_PATH",
    "FEEDBACK_STATE_PATH",
    "FEEDBACK_MEMORY_PATH",
    "SENDER_PROFILE_PATH",
)

for _attr in STORE_PATH_ATTRS:
    _p = getattr(backend_main, _attr)
    assert str(_p).startswith(str(_STORE_TMP_DIR)), (
        f"store isolation broken: {_attr}={_p} is not under {_STORE_TMP_DIR}"
    )

# Session guard: any test that evicts/re-imports app modules must restore the
# original objects (see sys_modules_guard below); this finalizer is the
# session-level safety net that makes the eviction leak structurally visible.
_ORIGINAL_MAIN = backend_main

# Registry used by register_sys_modules_restore() / sys_modules_guard.
_SYS_MODULES_RESTORES: list[tuple[str, object | None]] = []


@pytest.fixture(scope="session", autouse=True)
def _restore_sys_modules_at_session_end() -> None:
    """Session-level restore of sys.modules entries registered via
    register_sys_modules_restore() by tests that mutate them."""
    yield
    while _SYS_MODULES_RESTORES:
        _name, _mod = _SYS_MODULES_RESTORES.pop()
        if _mod is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _mod


def register_sys_modules_restore(name: str) -> None:
    """Register the CURRENT sys.modules[name] (or its absence) for restore.

    Any test that mutates sys.modules for an app module MUST call this BEFORE
    the mutation (directly, or via the sys_modules_guard fixture).  The
    hygiene meta-test (tests/test_subprocess_and_sysmodules_hygiene.py)
    enforces this structurally.
    """
    _SYS_MODULES_RESTORES.append((name, sys.modules.get(name)))


@pytest.fixture
def sys_modules_guard() -> None:
    """Function-scoped guard for tests that mutate sys.modules.

    Usage: guard("main") immediately before the mutation.  The original
    object is restored at test teardown AND registered for session-end
    restore as a second net.
    """
    saved: dict[str, object | None] = {}

    def _register(name: str) -> None:
        if name not in saved:
            saved[name] = sys.modules.get(name)
        register_sys_modules_restore(name)

    yield _register

    for _name, _mod in saved.items():
        if _mod is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _mod


@pytest.fixture(scope="session", autouse=True)
def _isolate_stores_to_tmp() -> None:
    """§1.1: Verify every persisted store resolves to the throwaway tmp dir.

    Since PHISHSHIELD_STORE_DIR is set before main.py is imported (above),
    the paths are correct by construction; this fixture asserts it so a
    regression fails loudly instead of silently writing to the repo.
    """
    for attr in STORE_PATH_ATTRS:
        p = getattr(backend_main, attr, None)
        assert p is not None and str(p).startswith(str(_STORE_TMP_DIR)), (
            f"{attr}={p} not redirected to {_STORE_TMP_DIR}"
        )
    yield


@pytest.fixture(autouse=True, scope="function")
def _per_test_store_bindings(request) -> None:
    """§A.1: Per-test binding check — self-naming offender report.

    After each test function, sha256 the 7 guarded stores. On first difference from
    the session-baseline, record the test name.  This makes the offender self-naming
    instead of leaving the session-end finalizer to report only "something changed".

    Rule: on first difference → print STORE-BINDING OFFENDER: <nodeid> <store> <field>
    and set baseline := current (so later tests report clean).
    """
    import hashlib
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    BACKEND_DIR = ROOT / "backend"
    DATA_DIR = ROOT / "data"

    # Only run when PHISHSHIELD_STORE_DIR is set (i.e. in test context)
    store_dir = os.environ.get("PHISHSHIELD_STORE_DIR")
    if not store_dir:
        yield
        return

    # Session baseline: compute hashes once per session (first call only)
    if not hasattr(_per_test_store_bindings, "_session_hashes"):
        _per_test_store_bindings._session_hashes = {}
        for label, p in _STORE_LABELS:
            if p.exists():
                with open(p, "rb") as f:
                    _per_test_store_bindings._session_hashes[label] = hashlib.sha256(f.read()).hexdigest()[:16]
            else:
                _per_test_store_bindings._session_hashes[label] = "-"

    # Per-test: compute hashes and diff
    cur_hashes = {}
    for label, p in _STORE_LABELS:
        if p.exists():
            with open(p, "rb") as f:
                cur_hashes[label] = hashlib.sha256(f.read()).hexdigest()[:16]
        else:
            cur_hashes[label] = "-"

    # Report any diff — only on first diff, then re-baseline
    diffs = {k: (v, _per_test_store_bindings._session_hashes.get(k, "-"))
        for k, v in cur_hashes.items()
        if v != _per_test_store_bindings._session_hashes.get(k, "-")}
    if diffs:
        # Collect test name for the report
        node = getattr(request, "node", None)
        test_id = getattr(node, "nodeid", "unknown") if node else "unknown"
        # Print the offender
        for store, (new_hash, old_hash) in diffs.items():
            print(f"STORE-BINDING OFFENDER: {test_id} {store} mtime_ns")
        # Re-baseline: update session hashes to current so later tests report clean
        _per_test_store_bindings._session_hashes = cur_hashes

    yield


@pytest.fixture(scope="session", autouse=True)
def _load_model_artifacts_once() -> None:
    """Load TF-IDF artifacts before API tests (CI runs backend/train_model.py first)."""
    backend_main.load_artifacts()


@pytest.fixture(autouse=True)
def _internal_api_key_for_tests(monkeypatch) -> None:
    """Default every test to a configured internal key (deny-by-default contract).

    Tests that exercise the unconfigured/placeholder state monkeypatch
    INTERNAL_API_KEY themselves and override this default.
    """
    monkeypatch.setattr(backend_main, "INTERNAL_API_KEY", "test-internal-key")


@pytest.fixture(autouse=True)
def _reset_scan_cache_for_tests(tmp_path, monkeypatch) -> None:
    """Avoid cross-test pollution from scan_cache / explanations (stable scores)."""
    app.state.scan_cache = OrderedDict()
    app.state.scan_explanations = OrderedDict()
    app.state.scan_rate_limits = {}
    monkeypatch.setattr(backend_main, "SCANS_DB_PATH", tmp_path / "scans.test.db")
    backend_main._session_records.clear()
    yield
    backend_main._session_records.clear()


@pytest.fixture
def sample_emails() -> dict[str, str]:
    return {
        "safe_project": "Subject: Project Update\nTeam meeting scheduled tomorrow.",
        "safe_report": "Monthly report attached. No action required.",
        "linkedin": "Your LinkedIn weekly digest is ready.",
        "otp_awareness": "We never ask for OTP or passwords.",
        "otp_scam": "Send OTP immediately to avoid account block.",
        "phishing_link": "Verify now: http://secure-login.xyz",
        "bec": "Process urgent wire transfer confidentially.",
        "delivery": "Pay INR 50 delivery fee: http://pay-delivery.xyz",
        "verify": "Account notice: http://verify-now.xyz",
        "tax": "Claim refund: http://refund-portal.xyz",
    }


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client