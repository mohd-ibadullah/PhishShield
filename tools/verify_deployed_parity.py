#!/usr/bin/env python
"""Deployed-parity verifier: the ONLY deploy verdict for the PhishShield backend Space.

Checks, in order:
1) Fetches the raw deployed main.py from the HF Space and sha256-hashes it.
2) Counts hardening markers in the DEPLOYED source: compare_digest, email_sha256,
   PHISHSHIELD_ENABLE_DOCS, FORBIDDEN_RAW_CONTENT_KEYS — each must be >= 1.
3) Unauthenticated live probes: GET /api/history must be non-200; GET /docs must be 404.

Exit code: 0 only if ALL of the above hold. Prints every count; no prose verdicts.

Usage:
    python tools/verify_deployed_parity.py
Environment overrides:
    PARITY_SPACE_URL   (default https://huggingface.co/spaces/Mohd1314234123/phishshield-backend)
    PARITY_RAW_TIMEOUT (default 30s)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request

SPACE_BASE = os.environ.get(
    "PARITY_SPACE_URL",
    "https://huggingface.co/spaces/Mohd1314234123/phishshield-backend",
).rstrip("/")
RUNTIME_BASE = "https://mohd1314234123-phishshield-backend.hf.space"
RAW_URL = f"{SPACE_BASE}/raw/main/main.py"
TIMEOUT = float(os.environ.get("PARITY_RAW_TIMEOUT", "30"))

MARKERS = [
    "compare_digest",
    "email_sha256",
    "PHISHSHIELD_ENABLE_DOCS",
    "FORBIDDEN_RAW_CONTENT_KEYS",
]


def _fetch(url: str, timeout: float = TIMEOUT) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "phishshield-parity-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001 — report, never crash the verifier
        print(f"FETCH-ERROR {url}: {type(exc).__name__}: {exc}")
        return 0, b""


def main() -> int:  # noqa: D103
    print(f"parity: fetching {RAW_URL}")
    status, body = _fetch(RAW_URL)
    if status != 200 or not body:
        print(f"parity: raw fetch failed status={status} bytes={len(body)}")
        print("PARITY: exit 1")
        return 1

    deployed_sha = hashlib.sha256(body).hexdigest()
    text = body.decode("utf-8", errors="replace")
    print(f"parity: deployed main.py sha256={deployed_sha} bytes={len(body)}")

    counts = {m: text.count(m) for m in MARKERS}
    markers_ok = all(c >= 1 for c in counts.values())
    print("markers " + json.dumps(counts, sort_keys=True) + (" OK" if markers_ok else " FAIL"))

    # Unauthenticated probes against the live runtime.
    h_status, _ = _fetch(f"{RUNTIME_BASE}/api/history", timeout=15)
    print(f"probe GET /api/history (unauthenticated): {h_status} -> {'OK' if h_status != 200 else 'FAIL'}")
    d_status, _ = _fetch(f"{RUNTIME_BASE}/docs", timeout=15)
    print(f"probe GET /docs (docs disabled): {d_status} -> {'OK' if d_status == 404 else 'FAIL'}")

    ok = markers_ok and h_status != 200 and d_status == 404
    print(f"PARITY: exit {'0' if ok else '1'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
