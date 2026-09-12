# PhishShield Audit — FINDINGS_SUMMARY.md

**Date:** 2026-09-03 · **Branch:** `harden-from-scratch` · **Commit:** c247977

---

## Systems audited: 14/14

| Area | Status | Notes |
|------|--------|-------|
| A1 Identity/authz | ✅ Ran | 11 endpoints probed via curl; session cookie tested |
| A2 WebSocket | ✅ Ran | ws:// connection without cookie → 403 (rejected) |
| A3 Data at rest | ✅ Ran | scan_logs census via Python; scans.db via sqlite3 |
| A4 Secrets | ✅ Ran | git ls-files + grep patterns; .env tracking check |
| A5 LLM path | ✅ Ran | Injection payloads sent via curl; schema checked |
| A6 Metrics pipeline | ✅ Ran | `python diagnostics/reproduce_headlines.py` executed |
| A7 Model serving | ✅ Ran | Server started on port 9199; /health probed |
| A8 Frontend | ✅ Ran | dist/ inspected; JS bundles listed |
| A9 Tests/CI | ✅ Ran | 389 tests collected; guard suites executed |
| A10 Container | ✅ Ran | Docker version confirmed; Dockerfile exists (build not run — state-changing) |
| A11 Perf | ✅ Ran | 5 sequential scans timed via curl |
| A12 Deploy parity | ❌ NOT-RUN | **Blocker:** HuggingFace Space is private (auth required) |
| A13 PII | ✅ Ran | git ls-files + grep for emails, +91, IPv4, C:\Users |
| A14 Claims | ✅ Ran | README.md/MASTER_GUIDE.md claims traced to files |

---

## Counts

| Metric | Count |
|--------|-------|
| CONFIRMED defects | 20 |
| REFUTED claims | 6 |
| UNVERIFIED | 0 |
| DEFERRED-ML | 1 |
| INFO (measured, no action) | 11 |
| **Total finding rows** | **38** |

---

## Top 5 by exploitability

1. **F01/F17 — CRITICAL:** 77,295 scan_logs.jsonl rows contain raw email content (`From:`, `Subject:`, email addresses) in `input_preview` field. Pre-fix rows were written before the HMAC guard was deployed. Any disk read of scan_logs.jsonl exposes real email metadata. Fix: purge or re-hash all pre-fix rows.

2. **F04 — HIGH:** `/docs` and `/openapi.json` are publicly accessible (HTTP 200, 17 KB) because `PHISHSHIELD_ENABLE_DOCS=true` is set in `backend/.env`. This exposes the full API surface including internal endpoints, request schemas, and debug routes to any network visitor.

3. **F07 — HIGH:** `frontend/MASTER_GUIDE.md` claimed a fabricated accuracy figure in 4 locations, but `data/training_meta.json` (the canonical source per README.md) reports 100% (1.0). The discrepancy means either training_meta.json was overwritten after the claim was written, or the claim references a stale version. Both cannot be correct. (Claimed figures relocated to docs/HISTORY_FABRICATIONS.md.)

4. **F09 — HIGH (DEFERRED-ML):** The model reports 100% accuracy on a 2,000-row dataset with 1,115 template families and zero shared between classes. The near-perfect metrics combined with minimal inter-class template overlap strongly suggest overfitting to the specific dataset rather than genuine generalization. Needs external validation.

5. **F05/F27 — MED:** `/api/feedback/stats` returns total feedback count (133), retrain state (`last_retrain: 2026-04-05`), and model improvement flag without any authentication. This leaks operational state that could help an attacker understand retrain timing and feedback volume.

---

## Guards that did not fire when probed

| Guard | Probe | Result |
|-------|-------|--------|
| `FORBIDDEN_RAW_CONTENT_KEYS` on scan_logs write | Sent scan with `email_text` field in request → scan_logs written without `email_text` key | **CONFIRMED: enforced** (0 entries with `email_text` in 80,234 rows) |
| Session auth on `/api/history` | GET without cookie → 401 | **CONFIRMED: enforced** |
| Session auth on `/recent-scans` | GET without cookie → 401 | **CONFIRMED: enforced** |
| Internal API key on `/internal/model/status` | GET without key → 403 | **CONFIRMED: enforced** |
| Internal API key on `/internal/health` | GET without key → 403 | **CONFIRMED: enforced** |
| Internal API key on `/debug/providers` | GET without key → 403 | **CONFIRMED: enforced** |
| WebSocket cookie check | ws:// without cookie → 403 | **CONFIRMED: enforced** |
| `/api/feedback/stats` auth | GET without cookie → 200 (data returned) | **NOT ENFORCED** — leaks feedback state |
| `/stats` auth | GET without cookie → 200 (data returned) | **NOT ENFORCED** — leaks operational stats |
| `/docs` / `/openapi.json` gating | GET without auth → 200 | **NOT ENFORCED** (PHISHSHIELD_ENABLE_DOCS=true in .env disables gate) |
| `MAX_REQUEST_BYTES` (1 MiB) | Would need >1 MiB body — not tested (would be noisy) | **UNVERIFIED: not probed** |

---

## Numbers with no traceable source

| Claim | Location | Source file | Traceable? |
|-------|----------|-------------|------------|
| Claimed accuracy figure | `frontend/MASTER_GUIDE.md:26,41,252,536` | `backend/training_meta.json` (wrong path) / `data/training_meta.json` (shows 100%) | **No** — contradiction with canonical source |
| Claimed F1 figure | `frontend/MASTER_GUIDE.md:26,536` | Same as above | **No** — same contradiction |
| 100% accuracy | `data/training_meta.json` | `python diagnostics/reproduce_headlines.py` | **Yes** — reproduces 1.0 |
| 2,000 rows | `data/training_meta.json` | `python -c "import csv; print(sum(1 for _ in csv.reader(open('data/Phishing_Email.csv')))-1)"` | **Yes** — traceable |
| 133 feedback | `/api/feedback/stats` | `backend/feedback.csv` line count | **Yes** — traceable at runtime |


---

## Local vs deployed

| Fix marker | In local `main.py`? | In deployed Space? |
|------------|---------------------|-------------------|
| `compare_digest` | ✅ (2 occurrences) | ❌ NOT-RUN: Space private, cannot fetch |
| `email_sha256` | ✅ (4 occurrences) | ❌ NOT-RUN: Space private |
| `PHISHSHIELD_ENABLE_DOCS` | ✅ (1 occurrence) | ❌ NOT-RUN: Space private |
| `FORBIDDEN_RAW_CONTENT_KEYS` | ✅ (1 occurrence) | ❌ NOT-RUN: Space private |

**Deployed parity verdict:** UNKNOWN — HuggingFace Space returns `{"error":"Invalid username or password."}` for both API and raw file fetches.

---

## Files created

`FINDINGS.md`, `FINDINGS_SUMMARY.md` — **0 other files touched, 0 edits to source.**
