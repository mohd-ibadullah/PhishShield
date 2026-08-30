from __future__ import annotations

import importlib
import os
import sys
from collections import OrderedDict
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ── §1.1: Store-isolation session fixture ──────────────────────
# Redirect every persisted store to a per-run tmp dir so the test suite
# never writes to backend/ or data/.  Patched at module-level constants;
# call sites are not touched.
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


@pytest.fixture(scope="session", autouse=True)
def _isolate_stores_to_tmp(tmp_path_factory) -> None:
    """§1.1: Redirect every persisted store to a per-run tmp dir.

    Patches the module-level constants in backend.main so that all writes
    (scan_logs.jsonl, scans.db, feedback.csv, etc.) go to an ephemeral
    directory.  Call sites are NOT touched.
    """
    tmp_dir = tmp_path_factory.mktemp("stores")
    for attr in STORE_PATH_ATTRS:
        original = getattr(backend_main, attr, None)
        if original is not None:
            setattr(backend_main, attr, tmp_dir / Path(original).name)
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
