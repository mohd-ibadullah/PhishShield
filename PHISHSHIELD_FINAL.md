# PhishShield W2 — Security Hardening Final Report

**Branch:** `harden-from-scratch`  
**Date:** 2026-08-31 (final)  
**Commits:** 17 (b3.1 through guard refactor + anti-vacuity + PORT fix)

---

## (1) What Is Now True

### Test Suite

```
381 collected, 380 passed, 1 skipped
```

- N1 = 381 collected across 42 pytest files (collected via `python -m pytest --co -q`)
- 1 test intentionally skipped: `test_deliberate_repo_write` (writes to real store). Skip reason documented.
- 10 new tests: anti-vacuity (10), self-proving isolation (1), data-minimization (7), parity (8), concurrency (1), meta-test (3)

**Ignored-file table:**

**Excluded from CI suite:** 9 scripts moved to `tools/` — see `tools/README.md` for manifest.
2 files in `tools/` contain real pytest test functions (`test_scan_simple.py` → `test_scan_and_broadcast`, `test_wsbroadcast.py` → `test_websocket_broadcast`); they require a live server on :8000 and are not part of the automated suite.

### Shape-Based Guard (§1)

Replaces list-based persistence checks with shape-based rules enforced on every record before write:

- Key ending in `_hash`/`_sha256`/`_digest`: value must match `^[0-9a-f]{16,64}$`
- Key ending in `_preview`/`_text`/`_body`: value must not be email substring
- `FORBIDDEN_RAW_CONTENT_KEYS`: must not be present

`validate_record()` called by `append_structured_scan_log` before every write. Rejection logged, not raised — no data loss on guard trigger.

**Anti-vacuity proof (§1.2):**
- Guard catches raw-text hash, 15-char hex, forbidden key, email substring in `_text`/`_hash` keys (10 tests PASSED)
- Fails when `FORBIDDEN_RAW_CONTENT_KEYS` is emptied (proven)
- Passes when restored (proven)

### email_sha256 (§2)

**Consumer:** `backend/main.py:7787` — `/api/history` endpoint returns `email_sha256[:16]` as redacted preview.

**Format:** Plain SHA-256 (not HMAC). Short messages (< 100 chars) are dictionary-recoverable.

**Dictionary attack (§2.3):**
```
stored_email_sha256_count=32
candidate_count=5000
inverted_count=0
```
Dataset emails are 114-382 chars — not dictionary-recoverable. But user-submitted short emails (e.g., "Hi") would be.

### JSONL Atomicity (§3)

**Line length stats:**
```
total_lines=80065, max_bytes=1653, p99=1144, lines_gt_4096=0
post_fix_max=940, post_fix_p99=860, post_fix_gt_4096=0
```

All lines under PIPE_BUF (4096 bytes). No cross-process atomicity concern for current data.

**Corrected atomicity claim:** threading.Lock for in-process serialisation. `O_APPEND` for offset atomicity. Cross-process atomicity for large lines is not guaranteed by POSIX. Current max line = 1653 bytes (well under PIPE_BUF). Single-worker verified (Dockerfile: `python -m uvicorn main:app`, no `--workers`).

**Stress test at max observed length (1653 bytes):**
```
UNLOCKED: 200 records × 20 threads → 165 lines, 160 parsed, 4 failures
LOCKED:   200 records × 20 threads → 200 lines, 200 parsed, 0 failures
```

### PORT=0 (§4)

**Source:** `PORT=0` is set by the Freebuff desktop tool runtime (the tool running this session). Not from any project config file.

**Fix:** `vite build` no longer reads PORT. Dev server reads `VITE_DEV_PORT` or `PORT` with fallback to 5173. Preview port hardcoded to 4173.

**Verified:** `PORT=0 pnpm build` passes, `pnpm typecheck` passes.

### Duplicate Appends (§5)

**Counts:**
```
JSONL: 80061 records, 69352 unique scan_ids, 1713 duplicate scan_ids, 12422 duplicate rows
SQLite: 121 scans (0 dup), 137 scan_explanations (0 dup)
```

**Mechanism:** All duplicates are pre-lock (have `input_preview`). All have same verdict across entries for the same scan_id. Same scan_id logged repeatedly with different timestamps over multiple days. Frontend has `retry: false`. Exact mechanism UNCONFIRMED — likely from old code's lack of lock causing repeated logging of same result, but cannot prove definitively from code alone.

**Idempotency guard:** SQLite already has duplicate check (`save_scan_to_db` line 1489: `SELECT scan_id FROM scans WHERE scan_id = ?`). JSONL is append-only by design — duplicates are tolerated but counted.

### Frontend

- `pnpm test` — PASSED
- `pnpm build` — PASSED (with `PORT=0`)
- `pnpm typecheck` — PASSED

### Live Space (deployment not updated)

All endpoints return 200 without session cookie. The W2 hardening is committed locally but not deployed.

### Diagnostics

```
metadata_metrics={"accuracy": 1.0, "f1_score": 1.0, "precision": 1.0, "recall": 1.0}
measured={"accuracy": 1.0, "csv_records": 2000, "eval_set_v1_records": 220, "f1_score": 1.0, "false_positive_rate": 0.0, "fp": 0, "precision": 1.0, "recall": 1.0, "test_rows": 400, "tn": 200, "train_rows": 1600}
caveat={"csv_records": 2000, "families_shared_between_classes": 0, "template_families": 1115}
```

---

## (2) Claims Removed Because Unprovable

| # | Claim | Why removed |
|---|-------|-------------|
| 1 | "O_APPEND provides atomicity for all writes" | PIPE_BUF applies to pipes, not regular files. Only true for writes < PIPE_BUF. Current max = 1653 bytes (under limit), but the claim was stated as universal. |
| 2 | "Duplicate mechanism is concurrent interleaving" | All duplicates are pre-lock, same-verdict, same-scan_id. Concurrent interleaving would produce different scan_ids. Exact mechanism UNCONFIRMED. |
| 3 | "input_hash served correlation" | Removed — no external consumer. scan_id serves correlation. |
| 4 | "email_sha256 is keyed (HMAC)" | It is plain SHA-256, not HMAC. Short messages are dictionary-recoverable. |
| 5 | "Frontend build was broken for 3.5 months" | Fixed this session. PORT=0 from Freebuff runtime, not a project config issue. |

---

## (3) Historical Data Purge Status

**NOT EXECUTED.** See `purge_py.txt` for exact DELETE statements.

### Per-store counts:

| Store | Total rows/lines | Rows with email_text | Rows with email_sha256 |
|-------|-----------------|---------------------|----------------------|
| scan_explanations | 137 | 86 | 51 |
| scans | 121 | 0 | 0 |
| scan_logs.jsonl | 80,065 | 0 (`input_preview`=77739 old) | 0 |

### Duplicate rate:

| Store | Total | Unique scan_ids | Duplicate scan_ids | Duplicate rows |
|-------|-------|----------------|-------------------|---------------|
| scan_logs.jsonl | 80,061 | 69,352 | 1,713 | 12,422 |
| scans | 121 | 121 | 0 | 0 |
| scan_explanations | 137 | 137 | 0 | 0 |

### Dictionary attack result:

```
stored_email_sha256_count=32
candidate_count=5000
inverted_count=0
Dataset emails: 114-382 chars (not dictionary-recoverable)
Short user-submitted emails (< 100 chars) would be recoverable
```

---

## (4) Git Log

```
51b7cac test(isolation): document unique coverage of skipped violation proof
f8c24aa fix(frontend): vite build never reads PORT; dev-only setting
4d525ed test(guard): anti-vacuity proof for shape-based persistence checks
5b816b1 fix(deployed-copy): bump Space submodule for shape-based guard
0595c69 refactor(guard): shape-based persistence validation replaces list checks
4bcf393 test(isolation): make meta-test self-proving on every run
6dd9144 fix(frontend): tolerate PORT=0 by falling back to 5173
caf4943 refactor(data): drop redundant input_hash field from JSONL writer
161319a fix(deployed-copy): bump Space submodule to include HMAC + data_constants
97e51db chore(tests): remove test_e2e_websocket.py (syntax error, never valid)
7db5694 fix(logging): serialise JSONL appends under threading.Lock; rename field
1a37797 fix(data): keyed HMAC digest replaces plaintext preview in log/DB persistence
ef984fc refactor(parity): compare imported values instead of source strings
5a203aa test(isolation): redirect persisted stores to tmp; add repo-write meta-test
6562e60 fix(deployed-copy): update Space copy submodule pointer (D2)
```

### Git Status

```
 M backend/sender_profiles.json  (never staged per instructions)
 M data/feedback_memory.json     (never staged per instructions)
```

No security-relevant changes remain uncommitted.

---

## (5) Final State

**CLOSED** (each with the command that proves it):
- Shape-based guard: `python -m pytest tests/test_guards_are_not_vacuous.py -v` → 10 passed
- Anti-vacuity: empty FORBIDDEN_RAW_CONTENT_KEYS → guard fails; restore → passes (proven)
- email_sha256 kept: consumer at `backend/main.py:7787` (`/api/history` redacted preview)
- Dictionary attack: 5000 candidates, 0 inversions (dataset emails 114-382 chars)
- JSONL atomicity: max 1653 bytes, 0 lines > 4096, locked stress clean at max length
- PORT=0 fixed: `PORT=0 pnpm build` passes, `pnpm typecheck` passes
- Duplicates: 1713 dup scan_ids (12422 rows), all pre-lock, mechanism UNCONFIRMED
- Skipped test: documented unique coverage (writes to real file)
- Full suite: `python -m pytest tests/ -q` → 381 collected, 380 passed, 1 skipped

**UNCONFIRMED** (each with what would confirm it):
- Duplicate mechanism: would need old server logs or a repro with the pre-lock code
- Whether multi-worker deployment would corrupt: would need `uvicorn --workers N` to be tested
- Whether `fsync` is warranted: would need a production incident

**NOT-RUN** (each with the exact blocker):
- Live Space cold-start latency: requires Space to sleep and wake
- Historical data purge: operator decision

The deployed Space is not updated, the historical stores still hold email-derived content, and the detector's only defensible measured capability remains the n=60 per-language slices plus the 400-row templated holdout with its 0-shared-family caveat.
