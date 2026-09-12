# tools/ — Integration Scripts

These are **not pytest tests**. They require a running PhishShield backend
server on `http://127.0.0.1:8000` and hit the HTTP API directly.

## Files

| File | Description | Requires |
|------|-------------|----------|
| test_scan_simple.py | `test_scan_and_broadcast()` — async scan + WebSocket broadcast test | **Converted** to tests/test_scan_broadcast.py (TestClient, no live server) |
| test_wsbroadcast.py | `test_websocket_broadcast()` — WebSocket marker broadcast test | **Converted** to tests/test_scan_broadcast.py (TestClient, no live server) |
| test_10_cases.py | 10-case production validation suite (phishing vectors) | Live server on :8000 |
| test_advanced_detection.py | Advanced detection vector testing | Live server on :8000 |
| test_e2e.py | End-to-end certification against /scan endpoint | Live server on :8000 + combined_test_dataset.json |
| test_harness.py | Comprehensive test harness with full dataset | Live server on :8000 + combined_test_dataset.json |
| test_phishshield_cases.py | PhishShield case testing | Live server on :8000 |

Moved to `tools/legacy-manual-tests/` (2026-09-12) because they cannot import
safely as plain modules in CI (they `from main import ...` at module level or
load local model weights on import):

| File | Why moved |
|------|-----------|
| test_script.py | imports backend `main` at module level (manual validation suite) |
| test_trust.py | imports backend `main` at module level (identical copy already lived in legacy-manual-tests/) |
| word_trajectory.py | loads `backend/models/securebert_model` weights on import (1GB+, gitignored) |

## How to run

```bash
# Start backend first
cd backend && uvicorn main:app --host 127.0.0.1 --port 8000

# Then run a script
python tools/test_10_cases.py
```

## How to run test functions via pytest

```bash
pytest tools/test_scan_simple.py::test_scan_and_broadcast -v
pytest tools/test_wsbroadcast.py::test_websocket_broadcast -v
```

## CI status

- **py_compile**: checked in CI (`tests/*.py + tools/*.py`)
- **pytest collection**: NOT part of CI suite (requires live server)
- **Module-import probe** (`tests/test_tools_manifest.py`): tools/*.py must import cleanly
- **Last verified**: commit 0f3a7bc, 2026-08-31
