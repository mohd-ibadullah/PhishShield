import sys
import os
import subprocess
import json
import time
import requests

results = {}

# 1. RUN PYTEST ON ROOT TESTS
print("=== 1. RUNNING PYTEST SUITE ===")
try:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--tb=no", "--timeout=10"],
        capture_output=True,
        text=True,
        timeout=60
    )
    results["pytest_stdout"] = p.stdout.strip()
    results["pytest_stderr"] = p.stderr.strip()
    results["pytest_exitcode"] = p.returncode
except subprocess.TimeoutExpired:
    results["pytest_stdout"] = "TIMEOUT after 60s"
    results["pytest_exitcode"] = -1
except Exception as e:
    results["pytest_stdout"] = f"ERROR: {e}"
    results["pytest_exitcode"] = -1

print("Pytest exit code:", results.get("pytest_exitcode"))
print("Pytest summary:", results.get("pytest_stdout", "")[-500:])


# 2. TEST /retrain ENDPOINT
print("\n=== 2. TESTING /retrain ENDPOINT ===")
try:
    r = requests.post("http://127.0.0.1:8000/retrain", json={}, timeout=15)
    results["retrain_status"] = r.status_code
    results["retrain_json"] = r.json()
except Exception as e:
    results["retrain_status"] = "ERROR"
    results["retrain_json"] = str(e)

print("Retrain response:", results.get("retrain_status"), results.get("retrain_json"))


# 3. TEST SHAP / EXPLAIN
print("\n=== 3. TESTING EXPLAIN / SHAP ENDPOINT ===")
try:
    r = requests.post("http://127.0.0.1:8000/explain", json={"scan_id": "nonexistent_or_test"}, timeout=10)
    results["explain_status"] = r.status_code
    results["explain_json"] = r.json()
except Exception as e:
    results["explain_status"] = "ERROR"
    results["explain_json"] = str(e)

print("Explain response:", results.get("explain_status"), results.get("explain_json"))


# 4. TEST FRONTEND BUILD (pnpm build)
print("\n=== 4. TESTING FRONTEND BUILD (pnpm -r build) ===")
try:
    p = subprocess.run(
        ["pnpm", "--filter", "@workspace/phishshield", "run", "build"],
        cwd="frontend",
        capture_output=True,
        text=True,
        timeout=60,
        shell=True
    )
    results["frontend_build_stdout"] = p.stdout.strip()
    results["frontend_build_stderr"] = p.stderr.strip()
    results["frontend_build_exitcode"] = p.returncode
except Exception as e:
    results["frontend_build_stdout"] = f"ERROR: {e}"
    results["frontend_build_exitcode"] = -1

print("Frontend build exit code:", results.get("frontend_build_exitcode"))
print("Frontend build output:", results.get("frontend_build_stdout", "")[-500:])

with open("backend/reports/deep_dive_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
