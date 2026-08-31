#!/usr/bin/env python3
"""§1.2: Reusable adversarial digest probe.

Run against production-shaped input on demand:
  python scripts/adversarial_digest_probe.py --key <PHISHSHIELD_PREVIEW_HMAC_KEY>

Scans 5 short emails, pre-computes HMAC for 500 candidates, reports matches.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

SHORT_EMAILS = [
    "Hi", "Hello", "Thanks", "OK", "Yes", "No", "Please help", "Urgent",
    "Call me", "Check this", "Subject: Test", "Subject: Hello",
    "Subject: Urgent", "Subject: Invoice", "Subject: Password reset",
    "Subject: Account verification", "Subject: Your OTP is 123456",
    "Subject: Meeting tomorrow", "Subject: Project update",
    "Subject: Action required", "Verify your account now",
    "Click here to claim your prize", "Your account will be suspended",
    "Send OTP immediately", "Wire transfer requested", "Invoice attached",
    "Password expires today", "Login alert from new device",
    "Your subscription expires", "Confirm your email address",
]
while len(SHORT_EMAILS) < 500:
    SHORT_EMAILS.append(f"Subject: Message #{len(SHORT_EMAILS)}")


def hmac_digest(key: bytes, text: str) -> str:
    return hmac.new(key, text.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True, help="HMAC key to test against")
    args = parser.parse_args()

    key = args.key.encode("utf-8")

    # Read stored digests from scan_explanations (in-memory or DB)
    import sqlite3
    db_path = ROOT / "backend" / "scans.db"
    if not db_path.exists():
        print("No scans.db found — nothing to probe.")
        sys.exit(0)

    db = sqlite3.connect(str(db_path))
    rows = db.execute("SELECT payload_json FROM scan_explanations").fetchall()
    db.close()

    stored = []
    for (pj,) in rows:
        try:
            o = json.loads(pj)
            v = o.get("email_sha256", "")
            if v:
                stored.append(v)
        except Exception:
            pass

    if not stored:
        print("No email_sha256 values found in scan_explanations.")
        sys.exit(0)

    # Pre-compute candidate digests
    candidate_digests = {hmac_digest(key, e): e for e in SHORT_EMAILS}

    matches = sum(1 for d in stored if d in candidate_digests)
    print(f"stored_count={len(stored)}")
    print(f"candidate_count={len(SHORT_EMAILS)}")
    print(f"matches={matches}")
    if matches > 0:
        print(f"FINDING: {matches} stored digests match candidate digests with this key")
    else:
        print("No matches — key provides protection against this candidate set")


if __name__ == "__main__":
    main()
