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

STORE_PATH_ATTRS = (
    "SCAN_LOG_PATH",
    "SCANS_DB_PATH",
    "FEEDBACK_CSV_PATH",
    "FEEDBACK_STATE_PATH",
    "FEEDBACK_MEMORY_PATH",
    "SENDER_PROFILE_PATH",
)


# §3: Set a dedicated HMAC key for tests — never falls back to INTERNAL_API_KEY
os.environ.setdefault("PHISHSHIELD_PREVIEW_HMAC_KEY", "test-hmac-key-for-ci-only")


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

# Manual integration scripts that hit a live HTTP server or run certification on import.
collect_ignore = [
    "test_advanced_detection.py",
    "test_harness.py",
    "test_e2e.py",
    "test_script.py",
    "test_scan_simple.py",
    "test_wsbroadcast.py",
    "test_10_cases.py",
    "test_phishshield_cases.py",
]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

backend_main = importlib.import_module("main")
app = backend_main.app

# Runtime self-check: the env knob really redirected every store path, and
# none of them points into the repo working tree.
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
def _restore_sys_modules_at_session_end():
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
def sys_modules_guard():
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
def sample_emails():
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
