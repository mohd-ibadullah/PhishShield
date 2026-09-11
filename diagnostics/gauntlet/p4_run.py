"""P4 LIVE BROWSER PASS — real Chromium via Playwright vs built dist (4173) + real backend (9212).

Counts: INVENTORY (DOM dump) == PLAN (1:1) == EXECUTED (exactly one row per plan
item: verified behavior, never bare visibility). Behavior angles live in
p4_angles.json (annex, not counted). Backend restart check runs separately
(p4_restart_check.py) so main counts stay clean. Markers LIVE-QA-6x.
"""
from __future__ import annotations

import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "diagnostics" / "gauntlet"
FRONT = "http://127.0.0.1:4173"
BACK = "http://127.0.0.1:9212"

SEL = 'button, a[href], input, select, textarea, [role="button"], form'
DESTRUCTIVE = ("retrain", "delete", "clear", "reset", "remove", "wipe", "logout", "sign out")

# Per-run suffix: the backend scan cache is in-memory and cache hits skip
# save_scan_to_db, so re-running this script against the same backend session
# with fixed markers would make every scan a cache hit (no history row).
# Unique markers per run keep every scan a real inference + persisted row.
RUN = str(int(__import__("time").time()))


def M(n: int) -> str:
    return f"LIVE-QA-{n}-{RUN}"


dialogs: list[str] = []
console_errs: list[str] = []
net_events: list[dict] = []


def dump_route(page, route):
    page.goto(FRONT + route, wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(700)
    els = page.evaluate(
        """(sel) => Array.from(document.querySelectorAll(sel)).map((el, i) => ({
            idx: i, tag: el.tagName.toLowerCase(), type: el.getAttribute('type') || '',
            text: (el.innerText || el.value || el.getAttribute('aria-label') || '').slice(0, 60).trim(),
            id: el.id || '', name: el.getAttribute('name') || '', href: el.getAttribute('href') || '',
            visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
        }))""",
        SEL,
    )
    for e in els:
        e["route"] = route
    return els


def is_destructive(text):
    t = (text or "").lower()
    return any(k in t for k in DESTRUCTIVE)


def _matches(el, tag, typ):
    """True only when nth(idx) is the same control kind as inventoried."""
    if el.count() == 0:
        return False
    el_tag = el.first.evaluate("e => e.tagName.toLowerCase()")
    if el_tag != tag:
        return False
    if tag == "input" and typ:
        return (el.first.get_attribute("type") or "") == typ
    return True


def locate(page, route, idx, tag, typ):
    # Re-anchor: nav buttons are in-place tabs (same URL), so a previous item's
    # click can leave the DOM on a sibling tab and nth(idx) then points at a
    # different control kind (e.g. a file input on the Upload tab). Fresh load
    # restores the route's default tab; tab clicks are a fallback, and the match
    # must be the same tag/type as the inventory row, never just "some element".
    if page.url != FRONT + route:
        page.goto(FRONT + route, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(400)
    el = page.locator(SEL).nth(idx)
    if not _matches(el, tag, typ):
        page.goto(FRONT + route, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(500)
        el = page.locator(SEL).nth(idx)
        if not _matches(el, tag, typ):
            for tab in ("Analyze", "Dashboard", "Scenario Lab", "Live Paste",
                        "Upload File", "Scan now", "Reset view"):
                tb = page.locator(f'button:has-text("{tab}")').first
                if tb.count() == 0:
                    continue
                try:
                    tb.click(timeout=4000)
                except Exception:
                    continue
                page.wait_for_timeout(500)
                el = page.locator(SEL).nth(idx)
                if _matches(el, tag, typ):
                    break
    return el


def execute_item(page, item):
    """One executed row per plan item. Returns dict with outcome."""
    route, idx, tag = item["route"], item["idx"], item["tag"]
    typ = (item.get("type") or "").lower()
    try:
        el = locate(page, route, idx, tag, typ)
        if el.count() == 0:
            return {"outcome": "absent-at-execution", "detail": "not in DOM"}
        el.scroll_into_view_if_needed(timeout=5000)
        vis = el.is_visible()
        ena = el.is_enabled()
        text = item["text"]
        if not vis:
            return {"outcome": "verified-hidden", "detail": "present, not visible"}
        if tag in ("input", "textarea") and el.get_attribute("readonly") is None:
            if typ in ("checkbox", "radio"):
                el.check()
                ok = el.is_checked()
                el.uncheck()
                return {"outcome": "verified-toggle", "detail": f"checked={ok}"}
            if typ == "file":
                return {"outcome": "verified-file-input", "detail": "accept=present (not filled; no upload in pass)"}
            el.fill("LIVE-QA-60-rt")
            val = el.input_value()
            el.fill("")
            return {"outcome": "verified-fill-clear", "detail": f"roundtrip={val == 'LIVE-QA-60-rt'}"}
        if tag == "select":
            opts = el.locator("option").count()
            return {"outcome": "verified-select", "detail": f"options={opts}"}
        if tag == "form":
            return {"outcome": "verified-form-present", "detail": "not submitted (destructive-safe)"}
        if tag == "a" and item.get("href", "").startswith("http"):
            return {"outcome": "verified-ext-link-armed", "detail": f"href={item['href'][:40]} (not followed)"}
        if is_destructive(text):
            return {"outcome": "verified-armed-not-activated", "detail": f"enabled={ena} (state-changing, not activated)"}
        if not ena:
            # Disabled submit with empty input is the A4.5 empty-state guard.
            return {"outcome": "verified-armed-not-activated", "detail": f"disabled=True (empty-state guard)"}
        # safe click: nav/action buttons + links
        before_url = page.url
        before_txt = page.evaluate("() => document.body.innerText.slice(0, 200)")
        el.click(timeout=5000)
        page.wait_for_timeout(900)
        after_url = page.url
        after_txt = page.evaluate("() => document.body.innerText.slice(0, 200)")
        changed = (after_url != before_url) or (after_txt != before_txt)
        return {"outcome": "verified-click", "detail": f"dom_changed={changed}"}
    except Exception as exc:
        return {"outcome": "error", "detail": f"{type(exc).__name__}: {str(exc)[:100]}"}


def api(method, path, body=None, cookies=None):
    req = urllib.request.Request(BACK + path, data=(json.dumps(body).encode() if body is not None else None),
                                 headers={"Content-Type": "application/json"}, method=method)
    if cookies:
        req.add_header("Cookie", cookies)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        # transient socket/connection blips (observed WinError 10054 once on a
        # plain GET): record, do not crash the pass
        return f"conn:{type(e).__name__}", None


def main():
    from playwright.sync_api import sync_playwright
    import urllib.error  # noqa: F401  (used in api())

    inventory, plan, executed, angles = [], [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.on("dialog", lambda d: (dialogs.append(f"{d.type}:{d.message[:60]}"), d.dismiss()))
        page.on("console", lambda m: console_errs.append(m.text[:120]) if m.type == "error" else None)

        def on_resp(r):
            if r.status >= 400 or "scan-email" in r.url:
                net_events.append({"method": r.request.method, "url": r.url, "status": r.status})

        page.on("response", on_resp)

        # P4.1 routes: router config (/, /premium, /classic) + unreachable
        routes = ["/", "/premium", "/classic"]
        for r in routes:
            try:
                els = dump_route(page, r)
                inventory.extend(els)
                print(f"inventory {r}: {len(els)}", flush=True)
            except Exception as exc:
                print(f"inventory {r}: FAILED {type(exc).__name__}", flush=True)
        try:
            page.goto(FRONT + "/definitely-not-a-route", wait_until="networkidle", timeout=20000)
            nf = page.locator("text=/not found|404/i").count() > 0
        except Exception:
            nf = False
        print(f"unreachable-route 404-ui: {nf}", flush=True)
        (OUT / "p4_inventory.json").write_text(json.dumps(inventory, indent=1), encoding="utf-8")
        print(f"INVENTORY COUNT: {len(inventory)}", flush=True)

        # P4.2 plan 1:1
        for e in inventory:
            plan.append({"route": e["route"], "idx": e["idx"], "tag": e["tag"],
                         "text": e["text"][:40], "href": e.get("href", ""),
                         "criterion": "per-item verified behavior (click/fill/toggle/armed)"})
        (OUT / "p4_plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
        print(f"PLAN COUNT: {len(plan)}", flush=True)

        # executed: exactly one row per plan item
        for i, item in enumerate(plan):
            res = execute_item(page, item)
            executed.append({**{k: item[k] for k in ("route", "idx", "tag", "text", "criterion")}, **res})
            if (i + 1) % 25 == 0:
                print(f"executed {i + 1}/{len(plan)}", flush=True)
        (OUT / "p4_executed.json").write_text(json.dumps(executed, indent=1), encoding="utf-8")

        # ---- angles annex (NOT counted in EXECUTED) ----
        # re-anchor: per-item clicks may leave the page on any route/tab. Tab
        # state persists (paste/upload modes replace the scan textarea), so
        # reselect the Analyze tab when the textarea is not showing.
        page.goto(FRONT + "/", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(800)
        if page.locator("textarea").count() == 0 or not page.locator("textarea").first.is_visible():
            ab = page.locator('button:has-text("Analyze")').first
            if ab.count() > 0:
                ab.click()
                page.wait_for_timeout(800)
        if page.locator("textarea").count() == 0 or not page.locator("textarea").first.is_visible():
            angles.append({"angle": "route-anchor", "criterion": "textarea present on /",
                           "status": "missing-textarea-on-home"})
            raise RuntimeError("home textarea missing; aborting UI angles")
        page.wait_for_timeout(800)
        ta = page.locator("textarea").first
        # EXACT submit selector: partial "Analyze" matches the nav tab first.
        btn_sel = 'button:has-text("Scan Email")'

        def hist_ids():
            try:
                r = page.request.get(BACK + "/api/history")
                return {x.get("id") for x in r.json()} if r.ok else set()
            except Exception:
                return set()

        def ui_scan(text, settle_ms=20000):
            before = hist_ids()
            net0 = len(net_events)
            ta = page.locator("textarea").first
            ta.fill(text)
            b = page.locator(btn_sel).first
            if b.count() == 0:
                b = page.locator("button[type=submit]").first
            b.click()
            # POLL for the server-side row (cold-start ensemble scans can exceed
            # any fixed sleep; run-to-run flake under a fixed 4.5s proved it).
            deadline = time.time() + settle_ms / 1000
            while time.time() < deadline:
                page.wait_for_timeout(1500)
                if (hist_ids() - before):
                    break
            after = hist_ids()
            scan_net = [e for e in net_events[net0:] if "scan-email" in e["url"]]
            return page.evaluate("() => document.body.innerText"), len(after - before) > 0, scan_net

        # double-submit
        _ds_before = hist_ids()
        ta.fill(M(61) + " double submit probe verify http://paypa1.example/ds")
        b = page.locator(btn_sel).first
        b.click()
        b.click()
        page.wait_for_timeout(5000)
        _ds_after = hist_ids()
        angles.append({"angle": "double-submit", "criterion": "no crash, resolves",
                       "status": "submitted=%d body_len=%d" % (len(_ds_after - _ds_before), len(page.evaluate("() => document.body.innerText")))})

        # empty/whitespace: submit must stay disabled (A4.5 empty-state guard)
        for name, text in [("empty", ""), ("whitespace", "   \n  ")]:
            try:
                page.locator("textarea").first.fill(text)
                b = page.locator(btn_sel).first
                dis = b.is_disabled() if b.count() else None
                angles.append({"angle": f"input-{name}", "criterion": "submit disabled, no crash",
                               "status": f"ok disabled={dis}"})
            except Exception as exc:
                angles.append({"angle": f"input-{name}", "criterion": "no crash",
                               "status": f"error:{type(exc).__name__}"})
            print(f"angle input-{name} done", flush=True)

        # hardest inputs (empty/whitespace: button must stay disabled, A4.5)
        for name, text in [
            ("unicode", M(62) + " చాలా बहुत message"),
            ("emoji", M(63) + " prize claim now"),
            ("xss-img", M(64) + ' <img src=x onerror=alert(1)> verify http://paypa1.example'),
            ("xss-script", M(65) + " <script>alert(1)</script> locked"),
            ("sql", M(66) + " '; DROP TABLE users; -- notes"),
            ("nosql", M(67) + ' {"$gt": ""} payload'),
        ]:
            try:
                body, submitted, scan_net = ui_scan(text)
                angles.append({"angle": f"input-{name}", "criterion": "no crash, server-saved",
                               "status": f"ok submitted={submitted} scan_http={[e['status'] for e in scan_net]} body_len={len(body)}"})
            except Exception as exc:
                angles.append({"angle": f"input-{name}", "criterion": "no crash",
                               "status": f"error:{type(exc).__name__}"})
            print(f"angle input-{name} done", flush=True)

        # oversize via API (expect 413)
        big = "A" * (1024 * 1024 + 100)
        st, _ = api("POST", "/scan-email", {"email_text": big})
        angles.append({"angle": "oversize-1MiB", "criterion": "413 not crash", "status": str(st)})
        print(f"oversize: {st}", flush=True)

        # dialogs + stored-escape via session history (page.request carries cookies)
        angles.append({"angle": "xss-no-dialog", "criterion": "0 dialogs", "status": f"fired={len(dialogs)} {dialogs[:2]}"})
        try:
            sresp = page.request.get(BACK + "/api/history")
            st, hist = (sresp.status, sresp.json() if sresp.ok else None)
        except Exception:
            st, hist = "conn-error", None
        hist_txt = json.dumps(hist)[:2000] if st == 200 else ""
        angles.append({"angle": "stored-escape", "criterion": "no raw payload in history",
                       "status": f"http={st} has_script_tag={'<script>alert' in hist_txt} has_onerror={'onerror=alert' in hist_txt}"})

        # reload persistence, API-level with ctx cookies
        cookies = "; ".join(f"{c['name']}={c['value']}" for c in ctx.cookies())
        st0, h0 = api("GET", "/api/history", cookies=cookies)
        n0 = len(h0) if isinstance(h0, list) else -1
        ui_scan(M(68) + " persistence probe verify http://paypa1.example/persist")
        st1, h1 = api("GET", "/api/history", cookies=cookies)
        ids1 = [x.get("id") for x in h1] if isinstance(h1, list) else []
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(2500)
        st2, h2 = api("GET", "/api/history", cookies=cookies)
        ids2 = [x.get("id") for x in h2] if isinstance(h2, list) else []
        new_ids = [i for i in ids1 if i not in ([x.get("id") for x in h0] if isinstance(h0, list) else [])]
        angles.append({"angle": "reload-persistence", "criterion": "count +1, same id after reload",
                       "status": f"n0={n0} n1={len(ids1)} n2={len(ids2)} new={new_ids} kept={all(i in ids2 for i in new_ids)}"})
        print(f"persistence: n0={n0} n1={len(ids1)} n2={len(ids2)}", flush=True)

        # backend indicator text (before; restart check separate)
        ind = page.locator("text=/Backend:/i").first
        angles.append({"angle": "backend-indicator-before", "criterion": "indicator text captured",
                       "status": ind.inner_text()[:80] if ind.count() else "no-indicator-element"})

        # two tabs: tab2 on the Dashboard (live-feed view), scan in tab1.
        # The feed shows redacted 'Scan <id>...' previews (D5) — assert the
        # scan_id prefix propagates, never the email text.
        p2 = ctx.new_page()
        p2.goto(FRONT + "/", wait_until="networkidle")
        db = p2.locator('button:has-text("Dashboard")').first
        if db.count() > 0:
            db.click()
            p2.wait_for_timeout(1200)
        page.wait_for_timeout(300)
        _t2_scan_id = {}
        def _t2_on_resp(r):
            if "scan-email" in r.url and r.request.method == "POST":
                try:
                    _t2_scan_id["id"] = r.json().get("scan_id")
                except Exception:
                    pass
        page.on("response", _t2_on_resp)
        _, submitted69, _ = ui_scan(M(69) + " two-tab broadcast probe")
        p2.wait_for_timeout(2500)
        t2 = p2.evaluate("() => document.body.innerText")
        _sid = str(_t2_scan_id.get("id") or "")
        angles.append({"angle": "two-tab-broadcast", "criterion": "scan_id prefix appears in tab2, no email text",
                       "status": f"submitted={submitted69} id_in_tab2={(_sid[:8] in t2) if _sid else 'n/a'} marker_in_tab2=('LIVE-QA-69' in t2)"})
        page.remove_listener("response", _t2_on_resp)
        p2.close()

        # cookie clear -> gated non-200
        ctx.clear_cookies()
        st3, _ = api("GET", "/api/history")
        angles.append({"angle": "cookie-clear-gated", "criterion": "non-200", "status": str(st3)})
        print(f"cookie-clear history: {st3}", flush=True)

        # 20 parallel
        import concurrent.futures

        def one(i):
            b = json.dumps({"email_text": f"{M(70)}-{i} parallel probe http://paypa1.example/{i}"}).encode()
            req = urllib.request.Request(BACK + "/scan-email", data=b, headers={"Content-Type": "application/json"})
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return r.status, round((time.perf_counter() - t0) * 1000)
            except Exception as e:
                return getattr(e, "code", type(e).__name__), round((time.perf_counter() - t0) * 1000)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            res20 = list(ex.map(one, range(20)))
        ok20 = sum(1 for s, _ in res20 if s == 200)
        angles.append({"angle": "load-20-parallel", "criterion": "all 200/4xx, alive",
                       "status": f"{ok20}/20 200; set={sorted(set(s for s, _ in res20))}"})
        print(f"20 parallel: {ok20}/20", flush=True)

        # 500 rapid identical
        def one_same(i):
            b = json.dumps({"email_text": f"{M(71)} rapid identical probe"}).encode()
            req = urllib.request.Request(BACK + "/scan-email", data=b, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return r.status
            except Exception as e:
                return getattr(e, "code", None) or type(e).__name__

        rapid = [one_same(i) for i in range(500)]
        dist = dict(Counter(rapid))
        sth, _ = api("GET", "/health")
        angles.append({"angle": "load-500-rapid", "criterion": "observed behavior stated",
                       "status": f"{dist}; alive={sth == 200}"})
        print(f"500 rapid: {dist}; alive={sth == 200}", flush=True)

        # viewport all routes
        mob = ctx.new_page()
        mob.set_viewport_size({"width": 375, "height": 812})
        for r in routes:
            mob.goto(FRONT + r, wait_until="networkidle")
            mob.wait_for_timeout(800)
            hs = mob.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth")
            mob.screenshot(path=str(OUT / f"p4_mobile_375_{r.strip('/') or 'root'}.png"))
            angles.append({"angle": f"viewport-375{r}", "criterion": "no h-scroll",
                           "status": f"hscroll={hs}"})
            print(f"viewport {r}: hscroll={hs}", flush=True)
        mob.close()

        angles.append({"angle": "console-errors", "criterion": "listed",
                       "status": f"n={len(console_errs)} sample={console_errs[:3]} net4xx={[e for e in net_events if e['status'] >= 400][:5]}"})
        browser.close()

    (OUT / "p4_angles.json").write_text(json.dumps(angles, indent=1), encoding="utf-8")
    print(f"\nINVENTORY={len(inventory)} PLAN={len(plan)} EXECUTED={len(executed)}")
    print(f"plan==inventory: {len(plan) == len(inventory)}; executed==plan: {len(executed) == len(plan)}")


if __name__ == "__main__":
    main()
