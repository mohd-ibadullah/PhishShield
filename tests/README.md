# tests/ — single-test files

Per the V18 row (EVIDENCE.md), files holding exactly one collected test are listed
here with the reason they hold one test. A single test per file is intentional when
the file guards one specific invariant that no other file covers. If a listed file's
assertion is later covered elsewhere, the duplicate file may be deleted (FR1 path in
the 2026-09-04 fix pass); if it remains the only coverage, it stays.

| File | What it asserts | Why it holds a single test |
|---|---|---|
| tests/test_all_files_import.py | every `.py` file under `tests/` compiles | one invariant (syntax validity of the whole test tree) — a second test would be the same assertion re-run |
| tests/test_ci_deselect_matches_ledger_gaps.py | CI `--deselect` set == `FIX_LEDGER.md` `gaps:` block; gap job executes the same node ids (C3/V31, added 2026-09-04) | one parity invariant between two files; the mutation pair is demonstrated externally, not as extra tests |
| tests/test_docs_metrics_match_artifacts.py | docs percentages trace to generated artifacts (T8/F07/F08) | one invariant: no untraceable percentages |
| tests/test_email_sha256_adversarial.py | short-email digests are not recoverable from the candidate set (§2.3) | one adversarial invariant; xfailed for the known short-email HMAC limitation |
| tests/test_feedback_marker.py | feedback.csv stores the marker hash, never plaintext email (D5) | one invariant: marker round-trip through the CSV |
| tests/test_jsonl_concurrency.py | concurrent scan_logs.jsonl writes do not corrupt the file (§4.5) | one stress invariant; further variants would duplicate the race check |
| tests/test_performance.py | P50/P95/P99 latency targets across 95 pipeline cases | one parametrized gate; the single test carries 95 cases |
| tests/test_performance_smoke.py | a scan completes and reports processing_ms within cap | one coarse smoke gate, deliberately kept separate from the detailed gate above |
| tests/test_retrain_gates.py | retrain is locked below threshold and respects feedback limits (T11) | one gate: threshold + limits are a single contract |
| tests/test_training_metadata_reproducibility.py | canonical metadata is trainer-owned and repo-relative (51) | one invariant: byte-identical regeneration |

Census method: `python -m pytest -q tests/ --collect-only 2>/dev/null | grep "::"` then
group by file prefix; files with count == 1 are listed above. The list is expected to
change as guards are added or merged; update this table whenever it does.