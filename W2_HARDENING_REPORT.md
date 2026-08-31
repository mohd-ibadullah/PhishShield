# PhishShield W2 — Security Hardening Report (Final)

**Branch:** `harden-from-scratch`
**Date:** 2026-08-31
**Suite total:** 372 passed + 1 xfailed + 1 skipped = **374 tests** (sharded across 41 files in 3 groups)

---

## Block 1 — Store Isolation

**What:** Every persisted-store path (`SCAN_LOG_PATH`, `SCANS_DB_PATH`, `FEEDBACK_CSV_PATH`, `FEEDBACK_STATE_PATH`, `FEEDBACK_MEMORY_PATH`, `SENDER_PROFILE_PATH`) resolves to a throwaway `tempfile.mkdtemp()` directory, set via `PHISHSHIELD_STORE_DIR` before `main.py` is imported.

**Evidence:**
- `tests/conftest.py:18-20`: `os.environ["PHISHSHIELD_STORE_DIR"] = str(_STORE_TMP_DIR)` runs before `importlib.import_module("main")` at conftest line 32.
- `tests/conftest.py:46-51`: Runtime self-check asserts every `STORE_PATH_ATTRS` entry starts with `_STORE_TMP_DIR`; fails loudly if redirect is broken.
- `tests/test_no_repo_store_writes.py:74-105` (`test_isolation_redirect_works`): Writes a marker to the redirected `SCAN_LOG_PATH`, asserts `backend/scan_logs.jsonl` snapshot unchanged. **PASSED** (shard 2).

---

## Block 2 — Repo-Write Detection

**What:** Session-scoped fixture captures `(size, mtime_ns, line_count)` of every store file before any test. Final assertion compares against post-run snapshots.

**Evidence:**
- `tests/test_no_repo_store_writes.py:60-63` (`_record_initial_store_state`): Session-scoped `autouse` fixture records `_snapshot(p)` for all 7 `STORE_FILES`.
- `tests/test_no_repo_store_writes.py:107-120` (`test_no_repo_store_writes`): Asserts `before == after` for every file. **PASSED** (shard 2).
- `tests/test_no_repo_store_writes.py:129-131` (`test_deliberate_repo_write`): Skipped by default (`reason="One-shot proof: writes to real file. Unique coverage vs self-proving test."`). Enabled only via `_TEST_PROVE_META_CATCHES_VIOLATION=1`. **SKIPPED** (shard 2) — skip reason text verified.

---

## Block 3 — Shape-Based Persistence Guard

**What:** `validate_record()` in `backend/main.py` enforces shape rules on every record before JSONL/SQLite write. Rules: `_hash`/`_sha256`/`_digest` keys must match `^[0-9a-f]{16,64}$`; `_preview`/`_text`/`_body` keys must not contain email substrings; `FORBIDDEN_RAW_CONTENT_KEYS` must not be present.

**Evidence:**
- `tests/test_guards_are_not_vacuous.py` — 11 tests **PASSED** (shard 2):
  - `test_guard_catches_raw_text_in_hash_field` — raw text in `_text` hash key rejected
  - `test_guard_catches_15_hex_value` — 15-char hex (<16 min) rejected
  - `test_guard_catches_65_hex_value` — 65-char hex (>64 max) rejected
  - `test_guard_catches_forbidden_key` — `FORBIDDEN_RAW_CONTENT_KEYS` present → rejected
  - `test_guard_catches_email_substring_in_text_key` — email substring in `_text` key → rejected
  - `test_guard_catches_email_substring_in_hash_key` — email substring in `_hash` key → rejected
  - `test_guard_passes_clean_record` — valid record accepted
  - `test_guard_passes_valid_hex_hash` — 32-char hex accepted
  - `test_guard_passes_valid_64hex_hash` — 64-char hex accepted

---

## Block 4 — Anti-Vacuity Proof

**What:** The guard is non-degenerate: it catches violations when enforcement is active and fails to catch when deliberately disabled.

**Evidence:**
- `tests/test_guards_are_not_vacuous.py:85` (`test_guard_vacuous_when_forbidden_keys_emptied`): Empties `FORBIDDEN_RAW_CONTENT_KEYS` → guard fails to catch forbidden key. **PASSED** (shard 2). This proves the guard is not vacuously true.
- `tests/test_guards_are_not_vacuous.py:100` (`test_guard_passes_clean_record`): Restores enforcement → clean record passes. **PASSED** (shard 2).
- `tests/test_data_minimization_e2e.py:195` (`test_mutation_proof_guard_fails_on_leak`): Injects email substring → guard rejects. **PASSED** (shard 1).
- `tests/test_data_minimization_e2e.py:219` (`test_mutation_proof_guard_passes_on_clean`): Clean record accepted. **PASSED** (shard 1).

---

## Block 5 — email_sha256 Digest

**What:** `/api/history` returns `email_sha256[:16]` as a redacted preview. Plain SHA-256 (not HMAC). Short messages (<100 chars) are dictionary-recoverable from a known-key attack surface.

**Evidence:**
- `tests/test_email_sha256_adversarial.py:51-60` (`test_short_email_digests_not_in_candidate_set`): With a known test key, short-email digests are recoverable. Test is **XFAIL(strict=True)** — documents the finding. **XFAILED** (shard 1): `Known test key makes short-email digests recoverable by design; if this passes unexpectedly, the adversarial assumption changed`.
- `tests/test_data_minimization_e2e.py:133` (`test_hmac_differs_from_plain_sha256`): Proves HMAC key produces different output than plain SHA-256. **PASSED** (shard 1).
- `tests/test_data_minimization_e2e.py:112` (`test_input_hash_removed_from_writer`): `input_hash` field no longer present in new records. **PASSED** (shard 1).

---

## Block 6 — JSONL Atomicity

**What:** All JSONL appends serialize under `threading.Lock`. Max observed line = 1653 bytes (under POSIX `PIPE_BUF` 4096). Single-worker deployment (`uvicorn main:app`, no `--workers` flag).

**Evidence:**
- `tests/test_jsonl_concurrency.py:34` (`test_concurrent_jsonl_writes`): 200 records × 20 threads, locked path → 200 lines, 200 parsed, 0 failures. **PASSED** (shard 2).
- `tests/test_data_minimization_e2e.py:152` (`test_no_email_content_in_new_records`): New records contain no email text content. **PASSED** (shard 1).

---

## Block 7 — PORT Fix + Ambient State

**What:** `PORT=0` (set by the Freebuff desktop tool runtime) no longer breaks the build or test suite. Vite build reads `VITE_DEV_PORT` or falls back to 5173. Ambient-state tests spawn a child pytest process with `PORT=0` and `PORT` unset, verifying the representative subset passes.

**Evidence:**
- `tests/test_ambient_state.py:107` (`test_suite_passes_with_port_zero`): Child pytest with `PORT=0` runs 3 representative tests (security_basics, data_minimization, endpoint_gating). **PASSED** (shard 1, 272.77s elapsed).
- `tests/test_ambient_state.py:118` (`test_suite_passes_with_port_unset`): Child pytest with `PORT` unset runs same subset. **PASSED** (shard 1).
- `tests/test_ambient_state.py:141` (`test_hmac_key_required`): Unset `PHISHSHIELD_PREVIEW_HMAC_KEY` → `RuntimeError` at startup, not silent fallback. Guard fixture restores `sys.modules["main"]`. **PASSED** (shard 1).
- `tests/test_ambient_state.py:160` (`test_main_module_restored_after_eviction`): `sys.modules["main"]` is the pre-test conftest-imported object. **PASSED** (shard 1).

---

## Block 8 — Store File Integrity (Before/After Subprocess Tests)

**What:** All 7 repo store files captured before and after running the full subprocess-spawning test (`test_ambient_state.py`). Zero byte deltas.

**BEFORE snapshot** (pre-shard 1):
```
backend/scan_logs.jsonl:        size=40321380  mtime_ns=1788154109943720700
backend/scans.db:               size=737280    mtime_ns=1788119382024076800
backend/feedback.csv:           size=20957     mtime_ns=1788129890279300500
backend/sender_profiles.json:   size=174       mtime_ns=1788132816180763000
data/feedback.csv:              size=58        mtime_ns=1778668906228055600
data/feedback_memory.json:      size=3063      mtime_ns=1788132816183077200
data/feedback_state.json:       size=209       mtime_ns=1778668906232675400
```

**AFTER snapshot** (post-shard 1, 106 passed + 1 xfailed including 3 child pytest invocations):
```
backend/scan_logs.jsonl:        size=40321380  mtime_ns=1788154109943720700
backend/scans.db:               size=737280    mtime_ns=1788119382024076800
backend/feedback.csv:           size=20957     mtime_ns=1788129890279300500
backend/sender_profiles.json:   size=174       mtime_ns=1788132816180763000
data/feedback.csv:              size=58        mtime_ns=1778668906228055600
data/feedback_memory.json:      size=3063      mtime_ns=1788132816183077200
data/feedback_state.json:       size=209       mtime_ns=1778668906232675400
```

**Deltas:** All 7 files: **UNCHANGED** (size_delta=0, mtime_diff=0).

---

## Meta-Tests

### Hygiene: sys.modules Mutation Guard
- `tests/test_subprocess_and_sysmodules_hygiene.py:122` (`test_sys_modules_mutations_are_registered_for_restore`): AST-scans all test files for `sys.modules[...]` subscript mutations; asserts each references `sys_modules_guard` or `register_sys_modules_restore`. **PASSED** (shard 3).

### Hygiene: Subprocess Pytest Bounding
- `tests/test_subprocess_and_sysmodules_hygiene.py:141` (`test_subprocess_pytest_invocations_are_bounded_and_redirect_stores`): AST-scans all test files for `subprocess.run`/`Popen`/etc. calling pytest; asserts each references `PHISHSHIELD_STORE_DIR` and targets specific `tests/test_*.py` files (not `tests/` directory). **PASSED** (shard 3).

### Hygiene: Runtime Identity Net
- `tests/test_subprocess_and_sysmodules_hygiene.py:167` (`test_main_module_is_unchanged_by_earlier_tests`): Asserts `sys.modules["main"]` is still the conftest-imported object. **PASSED** (shard 3).

---

## Suite Arithmetic

| Shard | Files | Passed | xfailed | skipped | elapsed |
|-------|-------|--------|---------|---------|---------|
| 1 (A-D) | 14 | 106 | 1 | 0 | 272.77s |
| 2 (E-P) | 13 | 142 | 0 | 1 | 88.37s |
| 3 (R-W) | 14 | 124 | 0 | 0 | 248.30s |
| **Total** | **41** | **372** | **1** | **1** | **609.44s** |

`sorted(union) == sorted(collected_by_pytest)`: **TRUE (41/41)**
`sorted(union) == sorted(ls(tests/) test_*.py)`: **FALSE (41 != 49)** — 8 files in `conftest.collect_ignore` (manual integration scripts: `test_advanced_detection.py`, `test_harness.py`, `test_e2e.py`, `test_script.py`, `test_scan_simple.py`, `test_wsbroadcast.py`, `test_10_cases.py`, `test_phishshield_cases.py`).

No file skipped or counted twice across shards.
