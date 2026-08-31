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
| test_script.py | Utility script | Live server on :8000 |
| test_trust.py | Trust/reputation testing | Live server on :8000 |

## How to run

```bash
# Start backend first
cd backend && uvicorn main:app --host 127.0.0.1 --port 8000

# Then run a script
python tools/test_scan_simple.py
python tools/test_10_cases.py
```

## How to run test functions via pytest

```bash
# These can also be collected by pytest if server is running:
pytest tools/test_scan_simple.py::test_scan_and_broadcast -v
pytest tools/test_wsbroadcast.py::test_websocket_broadcast -v
```

## CI status

- **py_compile**: checked in CI (`tests/*.py + tools/*.py`)
- **pytest collection**: NOT part of CI suite (requires live server)
- **Last verified**: commit 0f3a7bc, 2026-08-31
