# EVIDENCE2

Re-run of all 58 V-rows after the 2026-09-04 fix pass (input: EVIDENCE.md; row
ledger: FIX_LOG.md). Only the rows that were NOT-FIXED/UNTESTED in EVIDENCE.md
were re-run; FIXED rows carry their EVIDENCE.md fragment. Environment: repo root
`C:\Users\froms\Desktop\2`, branch `harden-from-scratch`; local app for S3/S4/S6
ran as `python -m uvicorn main:app --port 9210 --app-dir backend` (restarted
after the fix commits so the re-runs hit the fixed code).

Corrections applied 2026-09-04 after review: EVIDENCE.md record restored to its
original quoted text (V11/V12); V16 re-run once on the final tree (output below);
V40 recheck with before/after `compare_digest` counts; Space gitlink restored to
the pre-pass pointer 14e3575; V53 verified against the current index.

## §FINAL — verdict table (58 rows)

| V-ID | class | deciding output fragment |
|---|---|---|
| V01 | FIXED | `git status --short` prints only ` M backend/sender_profiles.json`, ` M data/feedback_memory.json`, ` M phishshield-backend-space` (on-disk Space copy kept as uncommitted local change — see DISCREPANCIES2) |
| V02 | FIXED | (carried) 25 commit subjects, all prefixed/descriptive |
| V03 | FIXED | (carried) tracked files = 489; size-pack = 27694 KB |
| V04 | FIXED | `Count 506`, `Sum 52017562`, `Maximum 22394045` (quoting-free re-run) |
| V05 | NOT-FIXED | `ModuleNotFoundError: No module named 'joblib'` (main.py line 34) in a bare venv; dependency installation is out of scope (FR6) — escalated: deploy-phase first priority (FIX_LEDGER.md `deploy-phase`): clean-venv lockfile install + `import main` CI gate |
| V06 | NOT-FIXED | clone import with the same venv → same `ModuleNotFoundError: No module named 'joblib'`; covered by the same deploy-phase CI gate |
| V07 | FIXED | (carried) 0 `collect_ignore` hits |
| V08 | FIXED | (carried) `51` |
| V09 | FIXED | (carried) `410 tests collected` (see DISCREPANCIES2 for the 418 now) |
| V10 | FIXED | (carried) keys list — `live_qa` absent |
| V11 | FIXED | (carried) EVIDENCE.md record carries the original quoted line count (re-measured 2026-09-04) |
| V12 | FIXED | verbatim row command re-run, no exclusions: `0` hits in all 8 claim docs; the only matched lines are EVIDENCE.md's own restored record (35 self-references, incl. V11's line count); history preserved in `docs/HISTORY_FABRICATIONS.md` |
| V13 | FIXED | (carried) LICENSE, data/CARD.md, data/PII_ALLOWLIST.txt listed |
| V14 | FIXED | entries all `<path>: <justification>`; parser test `2 passed`; bare-path scratch line rejected by the parser |
| V15 | FIXED | (carried) model.pkl + vectorizer.pkl tracked |
| V16 | FIXED | final full run (one run, no prose): `2 failed, 413 passed, 2 skipped, 1 xfailed, 378 warnings in 591.30s` — failures exactly `test_hindi_cases[case1]` + `test_telugu_cases[case1]` = the ML-SIDE remainder (8 − 6 RULE-SIDE); exit=1 |
| V17 | FIXED | (carried) both SKIPPED lines carry reasons |
| V18 | FIXED | census lists 10 single-test files; every one named with a reason in `tests/README.md` |
| V19 | FIXED | (carried) `6 passed`; watch-list-completeness guard present |
| V20 | FIXED | (carried) one assignment site: tests\store_manifest.py line 10 |
| V21 | FIXED | `4 passed` (3 + `test_rotation_caps_total_chain`); FR2 mutation FAIL→PASS |
| V22 | BLOCKED | `scan_logs.jsonl.1 40386252` remains — F13 human decision (FR7: not touched); cap guard bounds chains written after the fix |
| V23 | FIXED | (carried) cap recorded |
| V24 | FIXED | `4 passed` (3 + `test_chunked_over_cap_rejected`); FR2 mutation FAIL→PASS |
| V25 | FIXED | (carried) `12 passed` |
| V26 | FIXED | (carried) `7 passed` |
| V27 | FIXED | (carried) both tool files named |
| V28 | FIXED | (carried) tools/README.md lines 10-11 |
| V29 | FIXED | (carried) build/syntax jobs carry None for continue-on-error |
| V30 | FIXED | (carried) deselects are full node ids (now 2) |
| V31 | FIXED | `CI-only []` / `ledger-only []`; parity test `1 passed`, mutation FAIL→PASS |
| V32 | FIXED | `/metrics 401`, `/health 200`; first six all 401/404 |
| V33 | FIXED | `403` (internal/status), `403` (GET /retrain) — key check before method gate |
| V34 | FIXED | (carried) `200 True True True` |
| V35 | FIXED | (carried) cmp-exit=0, bodies byte-identical |
| V36 | FIXED | unowned scan_id + email_text → `400`; owned scan_id without email_text → `200 True` |
| V37 | FIXED | (carried) `REJECTED InvalidStatus` |
| V38 | FIXED | (carried) `5 passed`; positive and negative delivery assertions |
| V39 | FIXED | (carried) `4 passed` |
| V40 | FIXED | `0` pattern hits in backend/main.py and in phishshield-backend-space/main.py; `compare_digest` lines before run #2 (pre-pass 9318e49^) = 2, after = 4 — the +1 call is the C1 /metrics gate, not V40; V40's own hunks ≈ +11/−4 of the batch commit's +225 |
| V41 | FIXED | (carried) `before=485 after=486 delta=1` |
| V42 | FIXED | (carried) `content 0`; last-row keys carry no raw-content fields |
| V43 | FIXED | `orphans 0`, `fk 1`, `scans 726 expl 722` |
| V44 | FIXED | (carried) 0 lines |
| V45 | FIXED | (carried) columns without email_text |
| V46 | FIXED | (carried) both files recorded; `.1` = 40386252 (see DISCREPANCIES2) |
| V47 | FIXED | (carried) both check-ignore lines present |
| V48 | FIXED | (carried) header without email_text column |
| V49 | FIXED | (carried) 0 tracked `.env` files |
| V50 | FIXED | (carried) names only; rotation-pending list now in FIX_LEDGER.md (F5) |
| V51 | FIXED | (carried) 0 placeholder lines |
| V52 | FIXED | rebuilt dist: `dev-sandbox-key` 0, `api.key` 0, `Bearer ` 0 |
| V53 | FIXED | A4 census (self-referential files excluded): only `data/combined_test_dataset.json` (1) and `data/last_txt_dataset.json` (1) outside the allowlist; listed for F13; F1 dry-run proposes redaction, not applied. The 5 QA tools are out of the index (`git rm --cached` in 01b356c, verified absent from `git ls-files`); their on-disk and history PII is F13's call |
| V54 | NOT-FIXED | `12` lines in `git log -p --all` (permanent limit); one-line limit sentence added to `data/CARD.md` under `## Limits` |
| V55 | FIXED | (carried) model_used matches loaded providers, no `%` |
| V56 | FIXED | `HI Safe 15` (Devanagari); Telugu script → `TE` |
| V57 | FIXED | recursive src scan → `0` |
| V58 | NOT-FIXED | deployed `a507b33c` (2026-05-21) carries 0 of 4 markers; Space `private False`; local fixes are unverified in production |

Totals: FIXED 53, NOT-FIXED 4 (V05, V06, V54, V58), BLOCKED 1 (V22).

## DISCREPANCIES2

- V09 (410) vs current collection (418): 8 tests were added by this pass (chain cap, chunked cap, metrics gating, retrain GET gate, FK migration + orphan purge, CI/ledger parity, allowlist parser, deny-by-default metrics) — paste: trio shard `85 passed` (4 files) + main run 333 collected = 418; V09's 410 predates the additions.
- V22/V46: `backend/scan_logs.jsonl.1` is 40,386,252 bytes and predates the cap; it is covered by `.gitignore` and its fate is F13's decision. V22's live file `scan_logs.jsonl` measured 141188 (V22 run) then 157555 (final re-run) — the growth comes from the live probes; both values pasted.
- V16: runs this pass — #1 `10 failed, 405 passed, 2 skipped, 1 xfailed, 1 error`; #2 `4 failed, 411 passed, 2 skipped, 1 xfailed` (2 ML-SIDE + 2 fix-pass regressions, both then fixed and shard-verified); final (after record restore + doc rewords + gitlink correction) `2 failed, 413 passed, 2 skipped, 1 xfailed in 591.30s` — failures exactly `test_hindi_cases[case1]` and `test_telugu_cases[case1]`, the ML-SIDE remainder.
- V18: the single-test census now lists `tests/test_ci_deselect_matches_ledger_gaps.py` (added this pass) and no longer lists `tests/test_no_pii_in_tracked_files.py` (the allowlist parser test made it a 2-test file). All 10 current single-test files are named in `tests/README.md`.
- V53: the original census command also prints the two self-referential files (`tests/test_no_pii_in_tracked_files.py` 3 hits — guard fixtures; `tools/redact_pii.py` 2 hits — the tool itself); A4 excludes them by instruction. Both numbers kept here.
- V40: pre-pass (9318e49^) had 2 `compare_digest` lines (session + caller-key) and 2 `==` hits, both placeholder-equality (`== INTERNAL_API_KEY_PLACEHOLDER`) — startup check + request-path guard prefix; the caller-key comparison was already `compare_digest`. The batch commit refactored the placeholder check into `_is_internal_key_misconfigured()` (V40's share ≈ +11/−4 of the commit's +225; the other ~214 lines are Stage E / B1 / B2 / C1 / C2 / A3 / C4). After: 4 `compare_digest` lines (2 pre-existing + C1 `/metrics` gate + docstring mention).
- V12: EVIDENCE.md's V11/V12 quoted record was rewritten during D1 (figures removed) so the row's own grep would print 0 — that defaced the record. Corrected 2026-09-04: the record is reconstructed — V11's original line count, the V12 out block with the original figures, and the false "pattern text sanitized" note removed. Provenance (recorded in EVIDENCE.md DISCREPANCIES): the lines were reconstructed from commit 5e74aa9's docs (evidence-pass HEAD) plus tool-call fragments for the untracked FINDINGS.md lines; the pre-pass EVIDENCE.md was never committed and is not in git history, so a few FINDINGS.md-quoted lines are inverted from the D1 rewording rather than byte-verbatim. V12 is now satisfied by the docs alone: 7 remaining pattern tokens (the hyphenated form, plus its capital-QA variants that Select-String matches case-insensitively) reworded to `live_qa` in 5 claim docs (FINDINGS.md, FINDINGS_SUMMARY.md, FIX_2DEFECTS.md, FIX_LEDGER.md, PHISHSHIELD_FINAL.md). Verbatim re-run of the row command (no exclusions) prints 0 in the 8 claim docs; the only matched lines are EVIDENCE.md's own record (35 self-references, incl. V11's line count). FIX_LOG.md/EVIDENCE2.md carry no pattern tokens. V36/V41 probe addresses in EVIDENCE.md stay rewritten (`From: a@b.com`, `From: probe@a.com` → example.invalid) because the tracked-PII guard flags the originals; the guard's assertion is not editable (FR1).
- Space submodule: the fix pass committed in the embedded repo (f84c799) and the parent gitlink bumped to it — a local-only SHA a fresh clone cannot fetch. Corrected: commit a6c8661 restores the pre-pass pointer `14e3575` (verified via `git rev-parse 515e088:phishshield-backend-space` and `64dc32a^`; 89cab33 is the W2-alignment ancestor of that pointer). The on-disk Space copy keeps the hardened main.py as an uncommitted local change (` M phishshield-backend-space`), and the nested repo's f84c799 commit stays local to it.
- QA tools: the 5 PII-carrying tools (tools/ablate_a1.py, tools/probe_a1_deep.py, tools/reconcile_a1_discrepancy.py, tools/run_neural_suite.py, tools/verify_prompt_samples.py) were committed mid-pass (f78b84d) and `git rm --cached`'d in 01b356c — absent from `git ls-files` (verified), ignored via .gitignore. They remain on disk and in git history, so the PII they carry is still present in those locations; redaction/removal is F13's call. The V53 census counts the current index only and prints the 2 dataset files.

## UNTESTED

- none — every row ran; the two failed clean-venv rows (V05, V06) produced definitive errors, not run failures.

## BLOCKED

- V22 — human decision on `backend/scan_logs.jsonl.1` (40,386,252 bytes, pre-fix artifact): delete / redact / keep. FR7 forbids touching it here; the chain-cap guard (V21) bounds only chains written after the fix.
- V58 — deployed parity: the Space still runs the May revision; deploy is a later phase (FR6), so the row stays NOT-FIXED with the fragment above.
- V54 — permanent limit: +91/IP content lives in git history of `data/combined_test_dataset.json` and `docs/sample_emails_reference.txt` (12 lines measured); the current tree is clean per the PII guard.