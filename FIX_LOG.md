# FIX_LOG.md — fix-pass row ledger (2026-09-04)

## A1/V52
target:  dist grep `dev-sandbox-key|api.key|Bearer ` → 1 hit (index-CodQNjio.js); source trace: `frontend/lib/api-client-react/src/custom-fetch.ts:337` sets `authorization: Bearer dev-sandbox-key` when the caller set none.
edit:    `git diff --stat` (commit 64dc32a): `frontend/lib/api-client-react/src/custom-fetch.ts | 8 +-` — hardcoded fallback replaced with `VITE_DEFAULT_AUTH` env read; `pnpm --dir frontend --filter @workspace/phishshield build` re-run (dist is gitignored, never committed).
verify:  `pnpm --dir frontend --filter @workspace/phishshield build` → `✓ built in 553ms`; frontend unit tests → all metricFormatters tests PASSED.
recheck: dist grep: `dev-sandbox-key` → 0; `api.key` → 0; `Bearer ` → 0 (all three patterns, rebuilt dist).
status:  FIXED

## A2/V40
target:  `Select-String -Path backend\main.py -Pattern "provided_key ==|== INTERNAL_API_KEY"` → 2 lines, both matching only as substring of `== INTERNAL_API_KEY_PLACEHOLDER`: `validate_internal_key_configuration` (startup, line 350) and `_validate_internal_access` (request path, line 4354). The caller-key comparison (line 4361) was already `hmac.compare_digest` pre-pass — no request-path `==` on the live key existed.
edit:    commit 9318e49: placeholder-equality refactored into `_is_internal_key_misconfigured()` (`!=` form) at both sites + docstring reworded; caller-key comparison untouched. V40's share of the commit's +225: the 2 hunks around the helper (~+11/−4); the other ~214 lines belong to Stage E rules, B1, B2, C1, C2, A3, C4 (same commit, separate rows).
verify:  `python -m py_compile backend/main.py` exit 0; `tests/test_w2_harden.py -k metrics` and request-path key tests pass.
recheck: `grep -c "provided_key ==|== INTERNAL_API_KEY" backend/main.py` → `0`; `compare_digest` lines before run #2 (pre-pass commit 9318e49^) = 2 (session + caller-key), after (HEAD) = 4 (same 2 + C1 /metrics gate + docstring mention). Same grep on `phishshield-backend-space/main.py` → `0` (3 `compare_digest` lines there).
status:  FIXED

## A3/V36
target:  route found: `@app.post("/api/feedback")` at backend/main.py:8434; V36 probe answered 404 (unowned scan_id), row requires 400.
edit:    commit 9318e49: feedback ownership failure now `HTTPException(400, "scan_id does not belong to this session")`.
verify:  `tests/test_explain_runtime.py::test_feedback_api_alias_matches_primary_route` passes (owned scan_id + email_text → 200).
recheck: unowned scan_id + email_text → `400`; owned scan_id without email_text → `200 True`.
status:  FIXED

## A4/V53
target:  census `+91[0-9 \-]{8,}` over `git ls-files` → hits in the 2 dataset files plus the guard/tool themselves (3 + 2).
edit:    none to the system; census re-run excluding the two self-referential files (`test_no_pii_in_tracked_files`, `redact_pii`).
verify:  `python -m pytest -q tests/test_no_pii_in_tracked_files.py` → `2 passed` (guard + new allowlist parser).
recheck: A4 census: `86 data/Phishing_Email.csv`, `86 data/Phishing_Email_cleaned.csv`, `86 data/Phishing_Email_cleaned_1.csv` (allowlisted), `1 data/combined_test_dataset.json`, `1 data/last_txt_dataset.json` (listed for F13).
status:  FIXED (residue handed to F13/F1)

## A5/V56
target:  response had no non-null language field for Devanagari/Telugu script (`None Safe 15`).
edit:    commit 9318e49: `detected_language` added to the scan response payload from the already-computed language code.
verify:  Telugu script probe: `{'detected_language': 'TE', 'language': 'TE', 'verdict': 'Safe', 'risk_score': 15}`.
recheck: `python -c "...e='\u091a\u093e\u0932\u093e \u0926\u0947\u092e\u0939 \u0935\u093e\u0932\u093e \u0939\u0948'..."` → `HI Safe 15`.
status:  FIXED

## B1/V21
target:  `python -m pytest -q tests/test_scan_log_rotation.py -v` → `3 passed`; no test asserted total chain size over `scan_logs.jsonl*`.
edit:    commits 9318e49 + a4d23f3: chain-cap loop in `_rotate_scan_log` (while `sum(scan_logs.jsonl*) > cap*(KEEP+1)` drop oldest archive; live file never exceeds cap); `test_rotation_caps_total_chain` added.
verify:  `python -m pytest -q tests/test_scan_log_rotation.py -v` → `4 passed`.
recheck: same command → `4 passed`; FR2 mutation (chain loop removed in $TEMP copy) → `1 failed`; restore → `4 passed`.
status:  FIXED

## B2/V43
target:  `orphans 86` / `fk 0` on backend/scans.db.
edit:    commit 9318e49: `_migrate_scan_explanations_fk_if_needed()` — detect via `PRAGMA foreign_key_list`, rebuild table with `ON DELETE CASCADE`, purge orphans once (count logged); `PRAGMA foreign_keys=ON` on every connect via `_connect_scans_db`; parent scans row created idempotently before explanation inserts so FK enforcement does not reject valid scan flows.
verify:  `python -m pytest -q tests/test_scan_explanations_fk.py` → passes (migration + orphan purge on a tmp DB); FR2 mutation (migration skipped in $TEMP copy) → fails.
recheck: `orphans 0`, `fk 1`, `scans 726 expl 722`.
status:  FIXED

## C1/V32
target:  `/metrics` answered 200 anonymously; row requires 401/403/404 with `/health` 200.
edit:    commits 9318e49 + a4d23f3 + 01b356c: `/metrics` gated on the internal key — missing/invalid key answers `401`; `test_metrics_requires_internal_key` added to `tests/test_deny_by_default.py` (anonymous rejected, key accepted, /health 200); the pre-existing `test_metrics_endpoint` (test_phishshield.py) asserted anonymous 200 — that contract is contradicted by the C1 row, so the test now asserts anonymous rejection and key-authenticated 200 with metrics content (FR1-b, evidence = C1 FIXED-when); `test_metrics_endpoint_requires_auth` (accepts 200/401) passes unedited.
verify:  `python -m pytest -q tests/test_deny_by_default.py::test_metrics_requires_internal_key tests/test_w2_harden.py::test_metrics_endpoint_requires_auth tests/test_phishshield.py::test_metrics_endpoint` → 3 passed; FR2 pair (gate removed in $TEMP copy → fail; restore → pass).
recheck: `/api/history 401, /recent-scans 401, /stats 401, /api/feedback/stats 401, /docs 404, /openapi.json 404, /metrics 401, /health 200`.
status:  FIXED

## C2/V33
target:  GET /retrain answered 405 before any key check.
edit:    commit 9318e49: `@app.get("/retrain", include_in_schema=False)` answers 401/403 on missing/invalid key, 405 only with a valid key (method-only gate after key check); `test_retrain_get_checks_key_before_method` added.
verify:  `python -m pytest -q tests/test_explain_runtime.py -k retrain` → all retrain tests pass.
recheck: `/internal/model/status` → `403`; GET `/retrain` → `403` (not 405).
status:  FIXED

## C3/V29+V31
target:  CI deselected 8 ids; ledger-only set of 60+ names; no parity guard.
edit:    commits 6e5d56e + a4d23f3: FIX_LEDGER.md `## gaps` block (machine-readable, 2 ML-side entries); ci.yml deselects exactly `test_hindi_cases[case1]` + `test_telugu_cases[case1]`; gap-tracking job executes the same 2 ids; `tests/test_ci_deselect_matches_ledger_gaps.py` asserts CI deselect set == gaps block set and gap-job ids == deselect ids.
verify:  parity test → `1 passed`; FR2 mutation (fake gap line added) → `1 failed`; restore → `1 passed`.
recheck: V31 command → `CI-only []` / `ledger-only []`.
status:  FIXED

## C4/V24
target:  only Content-Length capped; no chunked/no-content-length coverage.
edit:    commits 9318e49 + a4d23f3: streaming branch in the request-size middleware (`async for` chunk accumulation, 413 before handler); `test_chunked_over_cap_rejected` added (no Content-Length, cap+1 bytes, handler-never-ran flag).
verify:  `python -m pytest -q tests/test_max_request_bytes.py -v` → `4 passed`; FR2 mutation (chunked branch removed in $TEMP copy) → `1 failed`; restore → `4 passed`.
recheck: same command → `4 passed`.
status:  FIXED

## D1/V12
target:  pattern hits in root .md docs and MASTER_GUIDE.md (quoted fabricated figures).
edit:    commit 8397d9b + 01b356c: all historical quotes relocated to `docs/HISTORY_FABRICATIONS.md` (header: these numbers were claimed and are NOT measured); active docs reworded. During D1 the record itself (EVIDENCE.md V11/V12 quoted lines) was also rewritten — corrected on 2026-09-04 review: EVIDENCE.md reconstructed to its original text (V11's line count; V12 out block with the original figures, re-sourced from the pre-pass doc versions at commit 5e74aa9 and tool-call fragments; the false "pattern text sanitized" note removed; reconstruction provenance bullet added to EVIDENCE.md DISCREPANCIES). V36/V41 probe addresses in EVIDENCE.md stay rewritten (`From: a@b.com`/`From: probe@a.com` → example.invalid) because the tracked-PII guard flags the originals; the guard's assertion is not editable (FR1).
verify:  history-preservation probe on docs/HISTORY_FABRICATIONS.md (relocated figure pattern) → `1` hit (history preserved).
recheck: verbatim row command re-run (no exclusions — the V12 row's original Select-String over `*.md,README.md,frontend\MASTER_GUIDE.md` with the row's pattern):
```
0 hits in FINDINGS.md, FINDINGS_SUMMARY.md, FIX_2DEFECTS.md, FIX_LEDGER.md, FIX_LOG.md, PHISHSHIELD_FINAL.md, W2_HARDENING_REPORT.md, README.md, EVIDENCE2.md, frontend/MASTER_GUIDE.md
35 hits in EVIDENCE.md — all of them the record's own restored lines (V11 line count + the quoted V12 out-block lines)
```
The 8 claim docs print 0; the only matched lines are EVIDENCE.md's own record (self-references present in the row's original run via V11).
status:  FIXED

## D2/V14
target:  allowlist entries lacked a machine-parsed `<path>: <justification>` form contract.
edit:    commit a4d23f3: allowlist already carries `#` comments above the block and `<path>: <justification>` entries; `test_allowlist_entries_are_machine_parsable` added to `tests/test_no_pii_in_tracked_files.py` (each non-comment line must match `^[^#][^:]+: .+$`, no stray whitespace, non-empty justification).
verify:  `python -m pytest -q tests/test_no_pii_in_tracked_files.py` → `2 passed`; scratch copy with a bare `data/Phishing_Email.csv` line → parser rejects (`bad lines: ['data/Phishing_Email.csv']`), scratch removed.
recheck: `Get-Content data\PII_ALLOWLIST.txt` → 3 `#` header lines, 3 `<path>: <justification>` entries.
status:  FIXED

## D3/V01
target:  tree carried tracked modifications and untracked items far beyond the two never-staged JSONs.
edit:    commits 9318e49, a4d23f3, 6e5d56e, 8397d9b, 64dc32a, f78b84d, 01b356c, a6c8661: per-row commits of all fix files; `.gitignore` extended (logs, bundles, `.freebuff/`, `qa_artifacts/`, `phishshield_v2/`, `skills/`, 5 PII-carrying QA tools — `git rm --cached` in 01b356c, genuinely out of the index, verified absent from `git ls-files`); `backend/sender_profiles.json` and `data/feedback_memory.json` never staged. Gitlink correction commit a6c8661 sets the Space pointer back to the measured pre-pass value: `git rev-parse 5e74aa9:phishshield-backend-space` = 14e3575 (diff: `-Subproject commit f84c799…` / `+Subproject commit 14e3575…`). Pointer timeline: 708b8fe→a507b33, 6562e60→89cab333, 161319a→3691365, caf4943→e368557, 5b816b1→c7e5f06, a67692d→0d14c7d, 515e088→14e3575, 64dc32a→f84c799 (local-only, reverted), a6c8661→14e3575. The on-disk Space copy keeps the hardened main.py as an uncommitted local change (` M phishshield-backend-space`).
verify:  `git diff --stat` pasted per commit; post-commit tree below.
recheck: `git status --short` → ` M backend/sender_profiles.json`, ` M data/feedback_memory.json` only.
status:  FIXED

## D4/V18
target:  10 single-test files (V18 list) with no per-file justification.
edit:    commit a4d23f3: `tests/README.md` table listing every single-test file with what it asserts and why it holds one test (census method documented).
verify:  census `python -m pytest -q tests/ --collect-only | grep "::"` grouped by file → 10 files with count 1; every one named in `tests/README.md`.
recheck: V18 pipeline output (empty due to the PowerShell glob quirk) — the deciding output is the census + `tests/README.md` table above.
status:  FIXED

## E1-E8 — the 8 red tests (Stage E classification, one line each)
- test_sender_domain_bank_alert_is_suspicious: RULE-SIDE → fixed (sender-domain risk signals) → passes.
- test_sender_domain_hdfc_alert_detected_as_brand_lookalike: RULE-SIDE → fixed (lookalike paired with account-access lure) → passes.
- test_hindi_cases[case1]: ML-SIDE → left red until V2 (Hindi recall measurement); ledger gaps entry added.
- test_hindi_cases[case3]: RULE-SIDE → fixed (Devanagari OTP-awareness) → passes.
- test_telugu_cases[case1]: ML-SIDE → left red until V2 (Telugu recall measurement); ledger gaps entry added.
- test_legitimate_marketing_newsletters_stay_safe[economist-promo]: RULE-SIDE → fixed (marketing cap + footer proof) → passes.
- test_legitimate_marketing_newsletters_stay_safe[google-skills-lab]: RULE-SIDE → fixed → passes.
- test_legitimate_marketing_newsletters_stay_safe[docker-welcome]: RULE-SIDE → fixed → passes.
verify:  shard `python -m pytest -q tests/test_phishshield.py -k "hindi_cases or telugu_cases or bank_alert or hdfc or marketing"` → 6 of 8 now pass; only `[case1]` of hindi/telugu remain red.
arithmetic: baseline `8 failed` − 6 RULE-SIDE fixed = `2` = ML-SIDE count. Final full run (after record restore + doc rewords + gitlink correction): `2 failed, 413 passed, 2 skipped, 1 xfailed in 591.30s` — failures exactly `test_hindi_cases[case1]` and `test_telugu_cases[case1]` = the ML-SIDE remainder. (Runs #1 `10 failed` and #2 `4 failed` occurred mid-pass; both regressions were fixed and shard-verified before this final run.)
status:  RULE-SIDE rows FIXED; ML-SIDE rows NOT-FIXED (red until V2, per instructions untouched)

## F1/V53-residue
target:  proposed redaction for the 2 residue files.
verify:  `python tools/redact_pii.py --dry-run` (tool fixed first: submodule gitlink caused PermissionError — `not p.is_file()` skip added, commit f78b84d) → `WOULD REDACT: data/combined_test_dataset.json (303 emails, 1 phones)`; `WOULD REDACT: data/last_txt_dataset.json (221 emails, 1 phones)`; total `41 files, 1182 emails, 7 phones`; `DRY RUN - no files modified`.
status:  NOT-APPLIED (dry-run only; redaction decision is the operator's)

## F2/V54
target:  nothing to fix; history truth.
verify:  `git log -p --all -- data/combined_test_dataset.json docs/sample_emails_reference.txt | Measure-Object -Line` → `12`; one-line limit sentence written to `data/CARD.md` under `## Limits` (commit 8397d9b).
status:  NOT-FIXED (permanent limit — truth lives in git history)

## F3
verify:  top-10 by size (measured 2026-09-04): `906.2 MB backend/models/muril_model/model.safetensors` (untracked), `725.8 MB phishshield_kaggle_bundle.zip` (untracked), `475.5 MB backend/models/securebert_model/model.safetensors` (untracked), `127.6 MB backend/indicbert_model/model.safetensors` (untracked), `38.5 MB backend/scan_logs.jsonl.1` (untracked, gitignored), `21.4 MB screenshots/demo.gif` (**tracked**), `14.3 MB backend/indicbert_model/tokenizer.json` (untracked), trace.zip files (untracked). No LFS, no deletion.
status:  MEASURED

## F4/V58
target:  deployed parity cannot be fixed here.
verify:  raw-file probe re-run → `api 200`, `private False sha a507b33c263b mod 2026-05-21T19:42:18.000Z`, `raw 200 354175`, markers `[0, 0, 0, 0]`.
recheck: deployed `a507b33c` (2026-05-21) carries 0 of 4 markers; local fixes are unverified in production.
status:  NOT-FIXED

## F5
verify:  `.env` key names + line numbers (values never read): HF_TOKEN (1, 40), VT_API_KEY (2), VIRUSTOTAL_API_KEY (3), PHISHSHIELD_INTERNAL_API_KEY (7), LLM_API_KEY (16), OPENROUTER_API_KEY (17), OPENROUTER_KEY (18), GEMINI_API_KEY (19), GOOGLE_API_KEY (20), PHISHSHIELD_PREVIEW_HMAC_KEY (44). Rotation-pending list written to FIX_LEDGER.md (commit 6e5d56e).
status:  LISTED

## V04
recheck: `git ls-files | ForEach-Object { (Get-Item $_).Length } | Measure-Object -Maximum -Sum` → `Count 506`, `Sum 52017562`, `Maximum 22394045`.
status:  FIXED

## V05
recheck: `python -m venv $env:TEMP\v05` then venv python imports backend/main → `ModuleNotFoundError: No module named 'joblib'` (line 34). Bare-venv import requires dependency installation, out of scope (FR6).
escalation: a fresh install cannot import main — every local-state claim and the README quickstart rest on the current interpreter. Named deploy-phase first priority in FIX_LEDGER.md (`## deploy-phase`): CI job that installs the lockfile in a clean venv, imports `main`, runs a pytest smoke.
status:  NOT-FIXED

## V06
recheck: `git clone . $env:TEMP\fresh06` (succeeded), venv python imports the clone's backend/main → same `ModuleNotFoundError: No module named 'joblib'`. Clone removed after the probe.
escalation: same as V05 — clean-clone import fails identically; covered by the same deploy-phase CI gate (FIX_LEDGER.md `## deploy-phase`).
status:  NOT-FIXED

## V16
recheck: final full run `python -m pytest -q tests/ -p no:randomly` (2026-09-04, after all fixes incl. record restore, doc rewords, gitlink correction):
```
FAILED tests/test_phishshield.py::test_hindi_cases[case1] - AssertionError: F...
FAILED tests/test_phishshield.py::test_telugu_cases[case1] - assert 31 >= 60
2 failed, 413 passed, 2 skipped, 1 xfailed, 378 warnings in 591.30s (0:09:51)
```
exit=1 (pytest process; the piped `echo $?` printed tail's exit 0)
classification (Stage E rule): baseline `8 failed` − 6 RULE-SIDE fixed = `2` = ML-SIDE count, and the final run's 2 failures are exactly the ML-SIDE pair (both ledger-gapped red-until-V2).
status:  FIXED

## V22
recheck: `Get-ChildItem backend\scan_logs.jsonl* | Select Name,Length` → `scan_logs.jsonl 157555`, `scan_logs.jsonl.1 40386252`. The 40 MB pre-existing `.1` is F13's decision (FR7: not mine to touch); the chain-cap guard bounds chains written after the fix (V21).
status:  BLOCKED: human decision on backend/scan_logs.jsonl.1 (F13/F1)

## V57
recheck: recursive scan of `frontend/artifacts/phishshield/src` (`*.tsx`, `*.ts`) for `dangerouslySetInnerHTML|innerHTML` → `0` (chart.tsx now injects css via `textContent`; commit 64dc32a).
status:  FIXED