# P4 — LIVE BROWSER PASS (this pass, sanity-gauntlet evidence — NOT a metric claim)

Stack: real Chromium (headless) via Playwright (throwaway venv `%TEMP%\liveenv`) against the
built dist served by `vite preview` (`http://127.0.0.1:4173`, same-origin proxy →
`http://127.0.0.1:9212`) and the real FastAPI backend (real stores). Nothing mocked.

## P4.1 Inventory (routes: `/`, `/premium`, `/classic` from router config; unreachable route check)

- `INVENTORY COUNT: 29` (log: `diagnostics/gauntlet/p4_run3.log`)
- Rows: `/` = 10, `/premium` = 9, `/classic` = 10
- Tag histogram: button = 26, textarea = 3; `<input>` = 0, `<select>` = 0, `<form>` = 0, `a[href]` = 0
- Unreachable route `/definitely-not-a-route` → 404 UI shown: `unreachable-route 404-ui: True`
- Full rows: `diagnostics/gauntlet/p4_inventory.json`

## P4.2 Plan == Inventory == Executed

- `PLAN COUNT: 29` (1:1 from inventory, each row has an observable criterion:
  click/fill/toggle/armed behavior — never bare visibility)
- `EXECUTED COUNT: 29` (exactly one executed row per plan item)
- `plan==inventory: True; executed==plan: True` (p4_run3.log)
- Executed outcome histogram: verified-click = 19, verified-armed-not-activated = 7
  (state-changing or empty-state-disabled controls: Clear draft ×2, Dismiss, Clear,
  Analyze Email ×2, Scan now — none activated), verified-fill-clear = 3 (the three
  textareas, roundtrip `LIVE-QA-60-rt`), error = 0
- Rows: `diagnostics/gauntlet/p4_plan.json`, `diagnostics/gauntlet/p4_executed.json`

## P4.3 Hardest input angles (annex, not counted in EXECUTED)

| angle | status (raw from p4_angles.json) |
|---|---|
| double-submit | `submitted=1 body_len=2973` |
| input-empty | `ok disabled=True` (A4.5 empty-state guard) |
| input-whitespace | `ok disabled=True` |
| input-unicode (`చాలా बहुत`) | `ok submitted=True scan_http=[200]` |
| input-emoji | `ok submitted=True scan_http=[200]` |
| input-xss-img `<img src=x onerror=alert(1)>` | `ok submitted=True scan_http=[200]` |
| input-xss-script `<script>alert(1)</script>` | `ok submitted=True scan_http=[200]` |
| input-sql `'; DROP TABLE users; --` | `ok submitted=True scan_http=[200]` |
| input-nosql `{"$gt": ""}` | `ok submitted=True scan_http=[200]` |
| oversize-1MiB | `413` (not a crash) |
| xss-no-dialog | `fired=0 []` |
| stored-escape | `http=200 has_script_tag=False has_onerror=False` |
| reload-persistence | `n0=7 n1=8 n2=8 new=['a28e7213d86f'] kept=True` |
| two-tab-broadcast | `submitted=True id_in_tab2=True marker_in_tab2=False` (scan_id prefix propagates, raw email text never) |
| cookie-clear-gated | `401` |
| load-20-parallel | `20/20 200; set=[200]` — V5.5 run was: single checkmaster session, claim corrected via re-run on 2026-09-12; evidence: unique-marker probe `latency_unique_probe.py` shows per-session limiter returns 429 after 10 in one window; settle probe (`settle_cache.py`, same cache-able payload 20x, one window) → `{200: 20}` = cache-hit path bypasses the limiter before it fires, so the unique-marker 429s and the 20/20-200 result are both explained; raw codes map in `p95_unique_final.md` |
| load-500-rapid | `{200: 500}; alive=True` (500 identical scans: 1 real inference + 499 in-memory cache hits, all 200, server alive) |
| viewport-375/ | `hscroll=False` (`p4_mobile_375_root.png`) |
| viewport-375/premium | `hscroll=False` (`p4_mobile_375_premium.png`) |
| viewport-375/classic | `hscroll=False` (`p4_mobile_375_classic.png`) |
| console-errors | `n=2` — both `POST /retrain → 403`, the intentional internal-key deny-by-default gate (`_validate_internal_access`, covered by `tests/test_deny_by_default.py`); UI surfaces it via toast, no crash/dialog |

Numeric fields (negative/NaN/inf): **N/A — the live DOM has zero `<input>` elements**
(26 buttons + 3 textareas), so there is no numeric control to fuzz; stated, not invented.

## P4.4 State angles — backend restart live indicator (timestamps UTC)

```
T0 2026-09-11T14:34:13+00:00 initial indicator: Backend: Connected ✅
T1 2026-09-11T14:34:13+00:00 taskkill /F /PID 2788 issued
T2 2026-09-11T14:35:10+00:00 indicator after kill: Backend: Offline ⚠️   (+57s, next 60s health tick)
submit-while-down: body_len=2080 crash=False dialogs=0
T3a 2026-09-11T14:35:16+00:00 backend restart issued
T3b 2026-09-11T14:35:17+00:00 restart subprocess returned
health after restart: True at 2026-09-11T14:35:27+00:00 (pid 2856)
T4 2026-09-11T14:36:10+00:00 indicator after restart: Backend: Connected ✅  (+43s)
dialogs_fired=0
```
(script: `diagnostics/gauntlet/p4_restart_check.py`, log: `diagnostics/gauntlet/p4_restart_check.log`)

## P4.4a Upload-file tab (checkmaster 2026-09-12)
- DOM check: `<input type="file">` count = **1** (dashboard.tsx:4157 code confirmed live).
- Real upload flow (Playwright `set_input_files` on a `.eml` probe): textarea filled with
  309 chars, mode auto-switched, scan ran → `FINAL VERDICT | SAFE ... TRUST 100/100 | RISK 0/100`
  (the probe .eml is an internal-looking note; backend classified it safe).
- Prior "probe couldn't find the input" finding: superseded — the tab was in a
  hidden state at the old probe's inventory point; with the tab active the input is
  reachable and the full flow (upload → parse → scan → verdict) works. Probe committed:
  `diagnostics/gauntlet/upload_probe.py`.

## P4.5 Load
- 20 parallel scans via API → `20/20 200`, server alive.
- 500 rapid-fire identical scans → `{200: 500}`, server alive. Observed behavior: the
  in-memory scan cache absorbs repeats (first scan real inference, subsequent identical
  scans cache hits, all 200); no rate-limit rejection observed for this burst.
- checkmaster re-run (2026-09-12, fresh boot): `20-parallel codes: {200: 20} | wall: 3.69 s`,
  all in-session. Caveat: a same-session burst above 10 scans per 60s hits the scan rate
  limiter (429); settle probe shows the cache-hit path returns 200 before the limiter
  fires, so the 20/20 is explained by cache reuse, no mystery; treat
  wall/20 as a floor, not per-scan inference time.
- Real per-scan latency with unique content, measured separately: warm inference is about
  150 to 200 milliseconds, first call in a window runs 450 to 700, and identical-text
  repeats are cache hits at 15 to 40 milliseconds. Full table and probe:
  `p95_unique_final.md`, `latency_unique_probe.py`.

## P4.6 Viewport 375×812
No horizontal scroll on `/`, `/premium`, `/classic`; screenshots:
`p4_mobile_375_root.png`, `p4_mobile_375_premium.png`, `p4_mobile_375_classic.png`.

## P4.7 Hardcode sweep (grep counts)
- `alert(|confirm(|prompt(` in `src`: **0**; in `backend/main.py`: **0**
- `Math.random()` in `src`: **2**, both exempt with file:line —
  `src/components/ui/sidebar.tsx:612` `SidebarMenuSkeleton` loading-shim width (visual only),
  `src/pages/dashboard.tsx:761` WS feed session key (uniqueness, not a result path)
- absolute `http://localhost|:8000|:9212` in `src`: **0**; in `backend/main.py`: **0**;
  in `phishshield-backend-space/main.py`: **0** (fixed: removed vestigial
  `http://localhost:5173` / `http://127.0.0.1:5173` dev origins from the CORS default
  allowlist — dev traffic is same-origin via the vite proxy; production sets
  `CORS_ALLOWED_ORIGINS` explicitly per render.yaml)
- Literal duplication of endpoint-served values: none found in the sweep greps above.

## Notes
- `POST /retrain → 403` is the designed deny-by-default internal-key gate
  (`_validate_internal_access`), surfaced by the UI as a toast; not a defect.
- The P4 harness was fixed to be re-run-safe: per-run unique markers
  (`LIVE-QA-<n>-<run>`) so repeated runs never collide in the backend's in-memory
  scan cache (cache hits skip `save_scan_to_db`), and type-matched re-anchoring so
  every inventoried control is exercised (0 absent-at-execution).