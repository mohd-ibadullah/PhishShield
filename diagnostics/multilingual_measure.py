#!/usr/bin/env python3
"""Measure per-language recall and FPR on the committed multilingual test cases."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import importlib
import importlib.util

main = importlib.import_module("main")
main.load_artifacts()
app = main.app

from httpx import ASGITransport, AsyncClient  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "mtc", str(Path(__file__).resolve().parents[1] / "tests" / "multilingual_test_cases.py")
)
mtc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mtc)

ALL = []
for c in mtc.HINDI_PHISHING_CASES:
    ALL.append(("Hindi", c["email"], c["expected_verdict"]))
for c in mtc.TELUGU_PHISHING_CASES:
    ALL.append(("Telugu", c["email"], c["expected_verdict"]))
for c in mtc.HINGLISH_PHISHING_CASES:
    ALL.append(("Hinglish", c["email"], c["expected_verdict"]))

# English cases from conftest sample_emails
ENGLISH = [
    ("English", "Verify now: http://secure-login.xyz", "phishing"),
    ("English", "Process urgent wire transfer confidentially.", "phishing"),
    ("English", "Pay INR 50 delivery fee: http://pay-delivery.xyz", "phishing"),
    ("English", "Monthly report attached. No action required.", "safe"),
    ("English", "Your LinkedIn weekly digest is ready.", "safe"),
    ("English", "We never ask for OTP or passwords.", "safe"),
]
ALL = ENGLISH + ALL


async def measure():
    transport = ASGITransport(app=app)
    results = {}
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for lang, email, expected in ALL:
            resp = await client.post("/scan-email", json={"email_text": email})
            data = resp.json()
            risk = data.get("risk_score", 0)
            key = lang
            if key not in results:
                results[key] = {
                    "phishing_expected": 0,
                    "safe_expected": 0,
                    "phishing_correct": 0,
                    "safe_correct": 0,
                }
            r = results[key]
            if expected == "phishing":
                r["phishing_expected"] += 1
                if risk >= 50:
                    r["phishing_correct"] += 1
                else:
                    print(f"  MISS: {lang} email risk={risk} expected=phishing")
            else:
                r["safe_expected"] += 1
                if risk < 50:
                    r["safe_correct"] += 1
                else:
                    print(f"  FP: {lang} email risk={risk} expected=safe")

    for lang in ["English", "Hindi", "Telugu", "Hinglish"]:
        r = results.get(lang, {})
        pe = r.get("phishing_expected", 0)
        se = r.get("safe_expected", 0)
        pc = r.get("phishing_correct", 0)
        sc = r.get("safe_correct", 0)
        recall = pc / pe if pe else None
        fpr = (se - sc) / se if se else None
        print(f"{lang}: n={pe + se} n_phish={pe} n_safe={se} recall={recall} fpr={fpr}")


if __name__ == "__main__":
    asyncio.run(measure())
