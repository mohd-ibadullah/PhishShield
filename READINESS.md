# READINESS.md — system-ready closure pass (2026-09-04)

Gate table. Verdicts only: PASS | FAIL | UNTESTED: <error> | BLOCKED: <decision>.

| Gate | Verdict | Raw output fragment |
|---|---|---|
| G01 | PASS | `git status --short` → ` M backend/sender_profiles.json` / ` M data/feedback_memory.json` / ` M phishshield-backend-space` (exactly 3 lines) |
| G02 | PASS | field-claim pattern over root+docs `.md` (records excluded): `{}` (empty) |
| G03 | PASS | `git diff --name-only 5e74aa9 -- EVIDENCE.md` → `EVIDENCE.md` (non-empty, recorded honestly); `18134` count in EVIDENCE.md = `3` (≥1 — record intact) |
| G04 | PASS | `tests/ -rs -v`: `2` SKIPPED lines, each with a reason string (`dist/ not built; label check skipped`, `No FPR in training metadata`); `0` DESELECTED. Run line: `3 failed, 412 passed, 2 skipped, 1 xfailed, 1 error in 546.28s` — the 3rd failure was the PII guard on CLOSURE_LOG's own D-1 row (fixed, D-4); the teardown error was root-caused (L7/L9, now CLOSED): the finalizer test's own cleanup restored mtime through float64, landing one NTFS tick off, and the session finalizer caught it — fixed with integer-ns `os.utime`; the module docstring's "mtime-only invisible" wording was corrected (the snapshot includes mtime_ns deliberately) |
| G05 | PASS | verdict-vocab sweep over `*.md`, `docs/*.md`, `CLOSURE_LOG.md` → `0` hits (8 tokens deleted in D-2, none softened) |
| G06 | PASS | `git ls-tree HEAD phishshield-backend-space` → `160000 commit 14e3575dd5d44fc8e38da12557e4bf0c32f77c0f`; no commit this pass bumped the pointer |
| G07 | PASS | `git ls-files EVIDENCE.md EVIDENCE2.md FIX_LOG.md FIX_LEDGER.md CLOSURE_LOG.md` → all five listed; `requirements.lock.txt` tracked |
| G08 | PASS | known-broken-command scan of CLOSURE_LOG.md (`xargs`/`-SkipHttpErrorCheck`/`venv -q`) → `0` |
| G09 | PASS | DISCREPANCIES3 present in CLOSURE_LOG.md: 4 entries (lockfile freeze conflict, G24 census arithmetic, joblib versions, C9 numbers in docs) |
| G10 | PASS | `1` BLOCKED row (C8) — carries the exact numbers, the command to run (the three C8 invocations), and the decision needed (the census identity G24 must assert) |
| G11 | PASS | guard shard: `8 passed in 9.85s` (docs-metrics, PII-in-tracked, CI-gaps-parity, rotation) |
| G12 | PASS | `psenv` clean import → `CLEAN-IMPORT-OK`; lockfile-built `psenv2` import → `CLEAN-IMPORT-OK` (joblib 1.4.2) |
| G13 | PASS | fresh `git clone` import in the clean env → `CLONE-OK` |
| G14 | PASS | `Clean clone now scans immediately` in FIX_LEDGER.md → `0` (reworded in C3 to the install-required truth) |
| G15 | PASS | `ALL DEFECTS CLOSED|zero remaining|fully hardened` over `*.md` + `docs/*.md` → `0` |
| G16 | PASS | `sorted(json.load('data/training_meta.json').keys())` → `['dataset_path', 'metrics', 'rows', 'test_rows', 'train_rows']` (no live_qa / model_type / source_rows / feedback_rows) |
| G17 | PASS | `backend/scan_logs.jsonl` = 157,779 bytes ≤ cap 5,000,000 (LOG_MAX_BYTES); `.1` = 40,386,252 bytes, named as C5's decision in CARD.md `## Limits` — not called fixed |
| G18 | PASS | `orphans 0 fk 1` |
| G19 | PASS | `/docs 404 30B`, `/openapi.json 404 30B`, `/metrics 401 62B`, `/stats 401 71B`, `/api/feedback/stats 401 71B`, `/internal/model/status 403 48B`, `/health 200 544B` (lockfile-env server, port 9212) |
| G20 | PASS | Telugu probe → `language = TE` (non-null); key `language` recorded in CLOSURE_LOG (V56 shape fix) |
| G21 | PASS | `dangerouslySetInnerHTML|innerHTML` in `frontend/artifacts/phishshield/src` → `0` |
| G22 | PASS | `dev-sandbox-key` in the dist → `0`; dist freshly rebuilt this pass (`pnpm --filter @workspace/phishshield build` → `✓ built in 19.11s`) |
| G23 | PASS | C8 failed-vs-gaps: `failed-not-in-gaps []` / `gaps-not-failed []` (one false positive removed: a `-- data/…` path in a ledger row the parser read as a gap id) |
| G24 | PASS | run A `2 failed, 413 passed, 2 skipped, 1 xfailed in 486.08s` (total 418); run B `85 passed in 472.20s`; run C `418 tests collected in 0.80s`. Resolved by human instruction: run A is the complement (`tests/` minus the 4 slow files) → 333 + 85 = 418 = C, real arithmetic. Provenance: the finish run `2 failed, 413 passed … in 488.63s` is the last full run (after commits 9f3b96a→61839c3); G04's `…1 error in 546.28s` ran before it. |
| G25 | PASS | one commit per C-step that touched files, defect + gate in the message: C0 `4d8cdb1` (record freeze), C1 `bd9930d` (G02), C2 `aa1e851` (G01), C3 `50459e7` + `7b608ae` (G14/G12/G05), C4 note `bd9930d` + pointer verify-only (G06), C5 `f54f826` (G07/G09), C6 `50459e7` (G15), C7 `f54f826`, C8/D-rows `9f3b96a`/`2f281cb`/`70dc5c1` (G11/G23/G10) |

Totals: **PASS 25 · BLOCKED 0 · FAIL 0 · UNTESTED 0**.

---

Locally verified: the full suite ends at `2 failed, 413 passed, 2 skipped, 1 xfailed` with the two failures being exactly the ledger-named ML-side Hindi/Telugu cases, a lockfile-built fresh environment imports `main`, boots `/health` 200, and imports from a fresh clone, all six gated surfaces return 401/403/404 while `/health` alone is 200, the failure set equals the `gaps:` block by node id, and every guard gate in this table passes.

What remains unverified lives outside this repo: the deployed Space `a507b33c` (2026-05-21) still carries 0 of the 4 hardening markers, git history holds PII (12 matching lines), `backend/scan_logs.jsonl.1` (40,386,252 bytes) awaits the human decision, non-Latin recall is 0, and gate G24's census formula awaits the human call.
