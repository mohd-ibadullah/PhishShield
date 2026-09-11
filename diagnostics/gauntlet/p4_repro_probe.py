"""Minimal P4 diagnosis probe: does a UI scan through the preview proxy persist a history row?"""
import json
import time

from playwright.sync_api import sync_playwright

FRONT = "http://127.0.0.1:4173"
BACK = "http://127.0.0.1:9212"
MARKER = "LIVE-QA-9%s repro probe verify http://paypa1.example/%s" % (time.time_ns() % 100000, time.time_ns() % 100000)

reqs: list[str] = []
resps: list[tuple[str, int]] = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()

    def on_req(r):
        if "scan-email" in r.url or "history" in r.url or "session" in r.url:
            reqs.append(f"{r.method} {r.url}")

    def on_resp(r):
        if "scan-email" in r.url or "history" in r.url:
            resps.append((r.url, r.status))

    page.on("request", on_req)
    page.on("response", on_resp)

    page.goto(FRONT + "/", wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(1500)

    ta = page.locator("textarea").first
    print("textarea_count:", page.locator("textarea").count(), "visible:", ta.is_visible() if page.locator("textarea").count() else "n/a")

    def hist():
        try:
            r = page.request.get(BACK + "/api/history")
            return r.status, r.json() if r.ok else None
        except Exception as e:
            return "conn-error", str(e)[:60]

    s0, h0 = hist()
    n0 = len(h0) if isinstance(h0, list) else -1
    print("history_before:", s0, n0)

    ta.fill(MARKER)
    page.wait_for_timeout(300)
    btn = page.locator('button:has-text("Scan Email")')
    print("scan_btn_count:", btn.count(), "disabled:", btn.first.is_disabled() if btn.count() else "n/a")
    btn.first.click()
    page.wait_for_timeout(2000)
    print("requests_after_click:", reqs)
    print("responses_after_click:", resps)
    # body text snippet after scan
    body = page.evaluate("() => document.body.innerText")
    print("body_has_verdict:", any(k in body for k in ("High Risk", "Phishing", "Safe", "Risk", "offline", "Offline")))
    print("body_snippet:", body[:400].replace("\n", " | "))
    # poll history
    deadline = time.time() + 20
    n1 = n0
    while time.time() < deadline:
        s1, h1 = hist()
        n1 = len(h1) if isinstance(h1, list) else -1
        if n1 > n0:
            break
        page.wait_for_timeout(1500)
    print("history_after:", s1, n1, "delta:", n1 - n0)
    if isinstance(h1, list) and h1:
        print("newest_row:", json.dumps(h1[0], default=str)[:400])
    browser.close()