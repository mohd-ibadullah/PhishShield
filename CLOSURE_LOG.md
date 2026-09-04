# CLOSURE_LOG.md — system-ready closure pass (2026-09-04)

Row ledger for C0–C9 and D-rows from gate failures. Row format:
`## C<n>` / `target:` / `edit:` / `verify:` / `recheck:` / `status:`.
Verdicts only: FIXED | NOT-FIXED | UNTESTED: … | BLOCKED: …

## C0
target:   none (records freeze)
edit:     commit 4d8cdb1 — CLOSURE_LOG.md created and committed; EVIDENCE.md/EVIDENCE2.md/FIX_LOG.md/FIX_LEDGER.md already tracked and clean
verify:   `git status --short` → ` M backend/sender_profiles.json`, ` M data/feedback_memory.json`, ` M phishshield-backend-space` only
status:   FIXED (G07: all five records tracked)

## C1
target:   Select-String over *.md,README.md,frontend\MASTER_GUIDE.md,docs\*.md with the field-claim pattern (any separator char) — 10 hits in 7 non-record docs: FINDINGS.md:40, FINDINGS_SUMMARY.md:79+84, FIX_2DEFECTS.md:44, FIX_LEDGER.md:84+89, PHISHSHIELD_FINAL.md:129, frontend/MASTER_GUIDE.md:7+928, docs/PHISHSHIELD_COMPLETE_OVERVIEW.md:7
edit:     deleted the 7 claim-residue rows (their full quotes already live in docs/HISTORY_FABRICATIONS.md); reworded the 3 process-meaning occurrences (QA-process sense, not the field claim) in MASTER_GUIDE/OVERVIEW; added a history section for the QA-field claim to docs/HISTORY_FABRICATIONS.md; EVIDENCE.md/EVIDENCE2.md untouched (record)
verify:   re-sweep → only EVIDENCE.md (7), EVIDENCE2.md (2), docs/HISTORY_FABRICATIONS.md (5) match; `'live_qa' in json.load(open('data/training_meta.json'))` → False
status:   FIXED (G02: gate list must print `{}`)

## C2
target:   `Select-String -Path FIX_LOG.md -Pattern "only.*sender_profiles"` → 0 lines, but the D3 recheck sentence still claimed a 2-line status
edit:     FIX_LOG.md D3 recheck rewritten to the 3-line truth: the two runtime JSONs plus ` M phishshield-backend-space` (intentional, uncommitted per C4)
verify:   `git status --short` prints exactly those 3 lines
status:   FIXED (G01)

## C3
target:   `pip install -r requirements.lock.txt` — the file does not exist (only backend/requirements.txt and backend/requirements-dev.txt); working interpreter joblib=1.4.2
target2:  FIX_LEDGER.md carried "Clean clone now scans immediately" (false until a clean-env install ran); gaps lines lacked the parameterized case ids; stray dash-bullets would corrupt C8's gaps parser
edit:     FIX_LEDGER.md D9 reworded to "clean clone + pip install -r requirements.lock.txt → no training step needed (model.pkl/vectorizer.pkl tracked)"; gaps lines now carry full node ids (test_hindi_cases[case1], test_telugu_cases[case1]); skipped/xfailed/deploy-phase bullets converted to prose without a leading dash; ci.yml gains the clean-env-import job (clean venv + lockfile install + import main)
verify:   G14 grep of the overclaim → 0; parity test (function-name comparison) unaffected by the bracketed ids
status:   BLOCKED: requirements.lock.txt does not exist — human must run `python -m pip freeze > requirements.lock.txt` (or promote backend/requirements.txt and add joblib==1.4.2) and approve committing it; the clean-env-import CI job stays red until then

## C4
target:   `git ls-tree HEAD phishshield-backend-space` → 14e3575dd5d…; `git submodule status --recursive` → fatal: no submodule mapping found in .gitmodules; .gitmodules absent
edit:     none to the pointer; PHISHSHIELD_FINAL.md gains the one-line manual-mirror note
verify:   pointer unchanged; no new commit inside the nested repo
status:   FIXED (G06)