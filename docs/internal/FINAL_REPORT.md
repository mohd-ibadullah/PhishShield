# FINAL REPORT

```
PHASE 0  0.1-0.7: findings + commands. Q->answer->cmd. Three claims refuted:
         guard removal disabled detector; 497.61s was reused duration; trio 78->79 came from
         test_scan_broadcast.py (other shard), not the 37+6+35 trio.
ITEM A   CLOSED — conftest.py now imports STORE_FILES and STORE_LABELS from tests/store_manifest.py
         (the single canonical list, all 7 stores including backend/feedback.csv). No duplicate
         hardcoded list remains. Per-test binding check (_per_test_store_bindings) watches all 7
         via the imported _STORE_LABELS. Verified: `pytest tests/test_no_repo_store_writes.py -v`
         passes all 6 tests including test_guard_watch_list_is_complete (7-path assertion).
ITEM B   CLOSED — Cross-case contamination test added and passing: test_case_1_sets_sentinel sets
         a marker in app.state.scan_cache; test_case_2_must_not_see_sentinel asserts the autouse
         _reset_scan_cache_for_tests fixture cleared it. Verified: both pass in 5.35s.
         `pytest tests/test_score_integrity.py::test_case_1_sets_sentinel
          tests/test_score_integrity.py::test_case_2_must_not_see_sentinel -v`
ITEM C   CLOSED — MAX_TOTAL_EVENTS=10000 and MAX_ROOMS=500 are enforced in
         backend/ws/connection_manager.py._evict_global_pending_locked(). Test fills to both caps,
         asserts total_queued == MAX_TOTAL_EVENTS. Mutation test proves caps fail when enforcement
         is removed. Note: cap=10000 is at or below the previously observed 20x903=18060 burst
         estimate; during such bursts, behavior is lossy (older events evicted), not "headroom".
         Verified: `pytest tests/test_scan_broadcast.py::test_pending_queue_is_bounded_across_rooms -v`
         passes in 5.81s.

CAP TEST EVIDENCE (grep output):
233-    total = sum(len(q) for q in cm._pending.values())
234:    assert total == cm._MAX_TOTAL_EVENTS, (
235:        f"Cap did not bind: total_queued={total} != MAX_TOTAL_EVENTS={cm._MAX_TOTAL_EVENTS}"
236-    )
--
257:    assert total_mutant > cm._MAX_TOTAL_EVENTS, (
258:        f"Mutation test failed: without enforcement, total={total_mutant} "
259:        f"should exceed MAX_TOTAL_EVENTS={cm._MAX_TOTAL_EVENTS}"
--
343:    size_bytes = len(serialized.encode())
346:    max_expected = cm._MAX_TOTAL_EVENTS * 100  # 100 B per event (generous)
347:    assert size_bytes < max_expected, (

ITEM D   CLOSED — Suite executed in two shards (runner caps at ~300 s; suite ~550 s single-run)
         404 collected (measured via --collect-only); 403 passed + 1 xfailed (sum of the two shard runs below); elapsed 134.86s + 177.30s = 312.16s (shard sum, not a single-run wall time)
         Shard 1: python -m pytest -q tests/ --ignore=tests/test_score_integrity.py --ignore=tests/test_score_integrity_tests.py --ignore=tests/test_explanation_integrity.py
           → 323 passed, 1 xfailed in 134.86s
         Shard 2: python -m pytest -q tests/test_score_integrity.py tests/test_score_integrity_tests.py tests/test_explanation_integrity.py
           → 80 passed in 177.30s
         Verification: 323 + 80 = 403 passed; 1 + 0 = 1 xfailed; 403 + 1 = 404 collected

ITEM E   CLOSED — pytest_configure preflight check added in tests/conftest.py. Fails clearly
         (config.error) when PHISHSHIELD_PREVIEW_HMAC_KEY is absent, instead of allowing a
         mass cascade of 134 RuntimeError failures (L8). Planted-violation test
         (test_hmac_key_required_planted_violation) proves the refusal path is non-vacuous:
         it injects a fake fallback, verifies it would be invoked, then confirms the real
         function refuses.

FILES CHANGED   tests/conftest.py — replaced hardcoded _STORE_FILES/_STORE_LABELS with import
                from store_manifest; added pytest_configure HMAC preflight check.
                tests/test_scan_broadcast.py — strengthened cap test: fills to MAX_TOTAL_EVENTS
                (10000 events), asserts total_queued == MAX_TOTAL_EVENTS, added mutation test
                proving caps fail without enforcement.
                tests/test_score_integrity.py — added cross-case contamination test
                (test_case_1_sets_sentinel + test_case_2_must_not_see_sentinel).
```
