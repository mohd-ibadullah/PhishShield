# PHASE 0 — Analysis Only (no edits)

## 0.1 — Guard change (STORE_FILES)

**Command:** `git diff -- tests/test_no_repo_store_writes.py`

**Before:** STORE_FILES watched 7 stores (5 lines):
- backend/scan_logs.jsonl
- backend/scans.db
- backend/feedback.csv
- data/feedback.csv
- data/feedback_state.json
- data/sender_profiles.json   ← REMOVED
- data/feedback_memory.json    ← REMOVED

**After:** STORE_FILES watches 5 stores — the two runtime-written files were removed, with a comment claiming they are "redirected to tmp by conftest" and that including them causes false positives.

**Verdict:** The guard was weakened from 7 → 5 watched files. The two removed files (`backend/sender_profiles.json` and `data/feedback_memory.json`) became unwatched.

## 0.2 — Failing thing (test_ws_marker_prefix_real.py)

**Command:** `ls tests/test_ws_marker_prefix_real.py` → file exists
**Command:** `grep -n "def test_\|scan_logs\|sender_profiles\|feedback_memory\|PHISHSHIELD_STORE_DIR" tests/test_ws_marker_prefix_real.py` → two tests only (`test_old_broadcast_code_path_leaks_marker`, `test_current_broadcast_preview_is_sanitized`); no reference to sender_profiles/feedback_memory/PHISHSHIELD_STORE_DIR.
**Command:** `git log --oneline -3 -- tests/test_ws_marker_prefix_real.py` → `f002b05 fix(surface): gate docs/openapi behind env flag; WS token verification + scoped broadcast (b3.5)`

**Original error quoted** (from `test_no_repo_store_writes.py` teardown, run `python -m pytest -q tests/test_no_repo_store_writes.py -v`):
```
AssertionError: Store files changed during the test suite:
  C:\Users\froms\Desktop\2\backend\scan_logs.jsonl:
    before: {'exists': True, 'size': 40371563, 'mtime_ns': 1788222989090650700, 'lines': 80201, 'sha256': '9d86e96373b5a0d08a4f73cb146eae5134a7c35f3c922b3ff937565cff29fd10'}
    after:  {'exists': True, 'size': 40371563, 'mtime_ns': 1788222989090650500, 'lines': 80201, 'sha256': '9d86e96373b5a0d08a4f73cb146eae5134a7c35f3c922b3ff937565cff29fd10'}
```
The changed field is **mtime_ns** (only field that differs: ...0650700 vs ...0650500, a 200-ns drift). size, lines, sha256 all identical.

## 0.3 — Writers of the two removed files

**Command:** `grep -rn "sender_profiles\|feedback_memory" backend/main.py | grep -i "write\|dump\|open(\|save\|json" | head -20`

| file | writer | respects PHISHSHIELD_STORE_DIR? |
|---|---|---|
| backend/main.py:114 | FEEDBACK_MEMORY_PATH = _store_path("feedback_memory.json", BASE_DIR.parent / "data" / "feedback_memory.json") | YES - _store_path checks _ENV_STORE_DIR (set from PHISHSHIELD_STORE_DIR) at import time; conftest sets env before import. |
| backend/main.py:116 | SENDER_PROFILE_PATH = _store_path("sender_profiles.json", BASE_DIR / "sender_profiles.json") | YES - same _store_path indirection. |
| backend/main.py:1327 | def save_feedback_memory(memory_payload) writes FEEDBACK_MEMORY_PATH | YES (uses the path constant) |
| backend/main.py:1371 | def save_sender_profiles(profiles) writes SENDER_PROFILE_PATH | YES (uses the path constant) |
| backend/main.py:3279 | save_sender_profiles(profiles) called at scan end | YES |
| backend/main.py:8190 | save_feedback_memory(feedback_memory) called at feedback submit | YES |

**Defect status:** The writers ALL resolve via _store_path, which reads PHISHSHIELD_STORE_DIR at import time. conftest.py sets the env var BEFORE importlib.import_module("main") (line 22 of conftest.py), so all paths ARE redirected to a tmp dir. The guard removal is therefore a suppression, not a fix for a real path-leak. The comment in the suppression is accurate: the two files ARE runtime-written, but the redirect already handles them — the only problem is the mtime_ns nanosecond drift on scan_logs.jsonl which is the actual false-positive source, not sender_profiles/feedback_memory.

## 0.4 — Reproduce the "redirect was not applied" hypothesis

**Commands:**
- `pytest -q tests/test_ws_marker_prefix_real.py -c /dev/null -rs` → 2 passed, 4 warnings in 6.62s (no errors)
- `pytest -q tests/test_ws_marker_prefix_real.py tests/test_scan_broadcast.py -rs` → 9 passed, 4 warnings in 7.62s (no errors)
- `pytest -q tests/test_no_repo_store_writes.py -v` → 4 passed, 4 warnings, 1 error — the error is ONLY test_finalizer_catches_real_store_write, and it is on scan_logs.jsonl mtime_ns drift (200ns), NOT on sender_profiles.json or feedback_memory.json (those two are no longer watched).

**Redirect verification** (prompt forbids a temporary print in the test module, so use the env-var print):
import backend.main as m; print(getattr(m,'STORE_DIR','<none>'))
→ STORE_DIR does not exist on the module (the env var is PHISHSHIELD_STORE_DIR). The paths are resolved via _store_path which reads os.environ["PHISHSHIELD_STORE_DIR"] at import time. Confirmed redirected by conftest's runtime self-check (asserts every STORE_PATH_ATTR is under _STORE_TMP_DIR).

**Verdict:** NOT REPRODUCED as a "redirect was not applied" failure — the redirect works (all 7 STORE_PATH_ATTRS assert under tmp). The single error seen is scan_logs.jsonl mtime_ns nanosecond drift (200ns) on the session teardown, a stat-based-guard weakness, NOT a store-path leak. No run produced a sender_profiles.json or feedback_memory.json path-leak error.

## 0.5 — Suite-shape audit (kills the 78→79 confusion)

**Commands:**
- `pytest -q --co tests/test_score_integrity.py tests/test_score_integrity_tests.py tests/test_explanation_integrity.py | tail -3` → collected counts: test_score_integrity.py (37), test_score_integrity_tests.py (6), test_explanation_integrity.py (35) = 78 total
- `pytest -q --co -q | tail -3` → the --co -q output is a deprecation warning line, but the full --co shows 389 tests collected in the repo
- `git diff --stat` → 8 files changed, 289 insertions, 112 deletions

**Per-file collected counts (current run):**
- tests/test_score_integrity.py: 37 tests
- tests/test_score_integrity_tests.py: 6 tests
- tests/test_explanation_integrity.py: 35 tests
- Sum = 78 (matches the earlier reported trio count)

**The +1 source:** The test_scan_broadcast.py file (the OTHER shard, not the trio) grew by 208 lines in the diff — it now contains test_pending_queue_is_bounded and other new tests. The trio itself did NOT grow (78→78). The "78→79" confusion is resolved: the trio stayed at 78; the net suite grew because test_scan_broadcast.py (a different shard) added tests. No edit added a test to the trio.

## 0.6 — Pending queue shape

**Command:** `grep -n "_pending\|_PENDING_MAX\|_PENDING_TTL" backend/ws/connection_manager.py`
- 26: self._pending: dict[str, list[tuple[dict[str, Any], datetime]]] = {}
- 27: self._PENDING_MAX = 20
- 28: self._PENDING_TTL_SECONDS = 60
- 104: room_pending = self._pending.setdefault(session_key, [])
- 105: room_pending.append((message, datetime.now(timezone.utc)))
- 106: if len(room_pending) > self._PENDING_MAX:
- 107:     self._pending[session_key] = room_pending[-self._PENDING_MAX:]

**Cap is PER ROOM (per session_key), NOT global.** _PENDING_MAX = 20 caps each room's queue independently. There is NO bound on the number of rooms — any number of unknown session_keys can each hold up to 20 events, so sum(len(q)) can grow to N_rooms x 20 unboundedly.

**test_pending_queue_is_bounded body** (tests/test_scan_broadcast.py line 294):
```python
async def test_pending_queue_is_bounded():
    """Broadcasting to many unknown keys must not grow _pending unboundedly."""
    from backend.ws.connection_manager import ConnectionManager
    cm = ConnectionManager()
    for i in range(100):
        await cm.broadcast({"type": "test", "idx": i}, session_key=f"unknown-{i}")
    total_pending = sum(len(v) for v in cm._pending.values())
    rooms = len(cm._pending)
    assert rooms <= 100, f"too many rooms: {rooms}"
    assert total_pending <= 100 * cm._PENDING_MAX, (
        f"_pending unbounded: {total_pending} entries across {rooms} rooms"
    )
```
**What it asserts:** It asserts total_pending <= 100 * _PENDING_MAX (per-room bound summed) AND rooms <= 100. It does NOT assert a GLOBAL cap independent of rooms — it asserts that the per-room cap holds, which is trivially true by construction of the code. The test passes because the invariant total_pending == 100 * 20 = 2000 is guaranteed by the per-room truncation, not because any global total is bounded. This test does NOT guard against unbounded growth in rooms — it would pass even if 1,000,000 unknown rooms each held 20 events.

## 0.7 — Analysis note

Q0.1 → guard reduced from 7→5 watched stores; sender_profiles.json and feedback_memory.json removed from watch list
Q0.1 → cmd: git diff -- tests/test_no_repo_store_writes.py
Q0.2 → error was scan_logs.jsonl mtime_ns 200ns drift (not a path leak); field = mtime_ns; cmd: pytest -v
Q0.3 → writers use _store_path(PHISHSHIELD_STORE_DIR) set by conftest before import; all 6 writers redirect correctly; cmd: grep -rn sender_profiles feedback_memory backend/main.py
Q0.4 → redirect works (all STORE_PATH_ATTR assert under tmp); error is mtime_ns nanodrift on scan_logs.jsonl only; NOT REPRODUCED as path-leak; cmd: pytest -v + env print
Q0.5 → trio stayed at 78 (37+6+35); +1 growth came from test_scan_broadcast.py (other shard), not the trio; cmd: pytest --co + git diff --stat
Q0.6 → _PENDING_MAX=20 is per-room, no global bound; test_pending_queue_is_bounded only asserts per-room cap (trivially true); cmd: grep + cat test
