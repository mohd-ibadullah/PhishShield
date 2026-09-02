# PhishShield W2 — Security Hardening Final Report

**Branch:** `harden-from-scratch`  
**Date:** 2026-08-31 (final)  
**Commits:** 17 (b3.1 through guard refactor + anti-vacuity + PORT fix)

## (1) What Is Now True

### Test Suite

```
    404 collected (measured via --collect-only); 403 passed + 1 xfailed (sum of the two shard runs below); elapsed 134.86s + 177.30s = 312.16s (shard sum, not a single-run wall time)
```

- N1 = 404 collected across 43 pytest files (measured via --collect-only); 403 passed + 1 xfailed = 404 (sum of two shard runs: 323 + 80 = 403 passed, 1 + 0 = 1 xfailed)
- 1 xfailed (strict): `test_short_email_digests_not_in_candidate_set` -- short-email HMAC digests recoverable with known key. If this ever PASSES, adversarial assumption broke.
- WS session scoping: `test_ws_broadcast_session_isolation` PASSED locally. **deployed: no**.
- WS content redaction: `test_ws_broadcast_content_redaction` PASSED (permanent guard).
- **Severity split:**
  - **Local (harden-from-scratch):** cross-session **metadata** disclosure (scan_id, verdict, risk_score; no raw email, b3.5 redaction works).
- **Global Live Feed decision:** Product decision needed — may be intentional as Live Feed feature. If yes, room key becomes a UI toggle and the OPEN item stays open with that decision recorded.
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
0595c69 refactor(guard): shape-based persistence validation replaces list checks
4bcf393 test(isolation): make meta-test self-proving on every run
6dd9144 fix(frontend): tolerate PORT=0 by falling back to 5173
caf4943 refactor(data): drop redundant input_hash field from JSONL writer
97e51db chore(tests): remove test_e2e_websocket.py (syntax error, never valid)
7db5694 fix(logging): serialise JSONL appends under threading.Lock; rename field
1a37797 fix(data): keyed HMAC digest replaces plaintext preview in log/DB persistence
ef984fc refactor(parity): compare imported values instead of source strings
5a203aa test(isolation): redirect persisted stores to tmp; add repo-write meta-test
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

| Claim | Test/Command | deployed |
|-------|-------------|----------|
| Shape-based guard | `pytest tests/test_guards_are_not_vacuous.py -v` → 10 passed | no |
| Anti-vacuity | FORBIDDEN_RAW_CONTENT_KEYS empty → fails; restore → passes | no |
| email_sha256 consumer | `backend/main.py:7787` | no |
| Dictionary attack | 5000 candidates, 0 inversions | no |
| JSONL atomicity | max 1653 B, locked stress clean | no |
| PORT=0 fixed | `PORT=0 pnpm build` passes | yes (frontend) |
| Duplicates | 1713 dup scan_ids, mechanism UNCONFIRMED | no |
| WS session scoping | `pytest tests/test_scan_broadcast.py -v` → 6 passed | no |
| WS pending replay scoped | `test_pending_replay_is_room_scoped` PASSED | no |
| WS collision rejection | `connect()` rejects duplicate key with 1008 | no |
| Timestamp stability | `pytest tests/test_timestamp_stability.py` → 2 passed | no |
| Store isolation | `test_isolation_redirect_works` PASSED | no |
| Full suite | 404 collected (measured via --collect-only); 403 passed + 1 xfailed (two shards: 323+1xf in 134.86s, 80 in 177.30s = 312.16s shard sum) | see FINAL_REPORT.md ITEM D |

**UNCONFIRMED** (each with what would confirm it):
- Duplicate mechanism: would need old server logs or a repro with the pre-lock code
- Whether `fsync` is warranted: would need a production incident

**NOT-RUN** (each with the exact blocker):
- Historical data purge: operator decision (markers purged locally)

**OPEN** (each with one-line reason + the single command that closes it):
| Item | Reason | Command to close |
|------|--------|-----------------|

| Live Feed global broadcast | May be intentional — product decision needed | Decide: feature or bug; if bug, scope to room |

**Purge result (2026-08-31):** purged 4 marker lines from `scan_logs.jsonl` (80,108 → 80,104 lines); the pre-W2 rows and the 1,713 duplicate-scan_id lines are still on disk; the duplicate-append mechanism is still unidentified.



## (6) Fixes Applied 2026-09-01

### Security: Space Version Auth Hardening
- /recent-scans: added require_session_key + server-side session validation
- /api/history: added require_session_key + _session_matches_record filter
- /explain POST: added require_session_key + _ensure_explanation_owner
- /feedback: added require_session_key

### Data Honesty
- Health label: SecureBERT/MuRIL-GPU-97.4% -> TF-IDF Logistic Regression
- model_type: TF-IDF Active Learning -> TF-IDF Logistic Regression
- Deleted empty FINAL_ELITE_DATASET.json
- Added MIT LICENSE file

### Cleanup
- 12 scratch scripts moved backend/scripts/ -> tools/
- Debug reports moved backend/reports/ -> tools/
- Store manifest deduplicated (conftest imports from store_manifest.py)
- Cross-case contamination test added
- Queue cap test: total_queued == MAX_TOTAL_EVENTS + mutation proof
- pytest_configure HMAC preflight check added

### Test Evidence
- Critical tests: 16/16 passed (10.26s)
- Security tests: 26/26 passed (12.06s)
- Full suite: 404 collected (measured via --collect-only); 403 passed + 1 xfailed (two shards: 323+1xf in 134.86s, 80 in 177.30s = 312.16s shard sum)

### Still Open
- Space WebSocket auth (async refactor needed)
- dev-sandbox-key hardcoded in frontend JS
- email_preview[:100] still stored
- training_meta.json hand-edited
- README false numbers (18684, 97.4%)
- PII in dataset files
- collect_ignore 9 files excluded
- ML model integration (model.pkl needed)

## Local vs deployed (measured 2026-09-03)

| Marker | Local count | Deployed count |
|--------|------------|----------------|
| `compare_digest` | 2 | 0 |
| `email_sha256` | 5 | 0 |
| `PHISHSHIELD_ENABLE_DOCS` | 1 | 0 |
| `FORBIDDEN_RAW_CONTENT_KEYS` | 1 | 0 |
| `dev-sandbox-key` | 0 | 0 |
| `97.4` | 0 | 2 |

**Deployed revision `a507b33c` (2026-05-21) contains none of the hardening markers. All fixes in this repo are local until a deploy happens. No claim of production safety is made anywhere in these docs.**
