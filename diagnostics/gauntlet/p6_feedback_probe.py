"""P6.1: feedback control surfaced on the scan-result panel (A4.6 closure).

Scan via the live UI, locate the feedback buttons (Correct/Incorrect -> safe/phishing),
click one, and confirm the backend records it (feedback stats endpoint delta).
"""
import json
import time

from playwright.sync_api import sync_playwright

FRONT = "http://127.0.0.1:4173"
BACK = "http://127.0.0.1:9212"
MARKER = "LIVE-QA-93-feedback verify http://paypa1.example/fb"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.goto(FRONT + "/", wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(1500)

    def fb_stats():
        try:
            r = page.request.get(BACK + "/feedback/stats")
            return r.status, r.json() if r.ok else None
        except Exception as e:
            return "conn-error", str(e)[:60]

    s0, st0 = fb_stats()
    print("feedback stats before:", s0, json.dumps(st0)[:120] if st0 else None)

    ta = page.locator("textarea").first
    ta.fill(MARKER)
    page.locator('button:has-text("Scan Email")').first.click()
    page.wait_for_timeout(12000)
    # feedback panel is section 9 of the Analyze tab result view
    fb_safe = page.locator('button:has-text("Mark as Safe")').first
    fb_phish = page.locator('button:has-text("Mark as Phishing")').first
    print("feedback buttons in DOM: MarkAsSafe=%d MarkAsPhishing=%d" % (fb_safe.count(), fb_phish.count()))
    if fb_safe.count() > 0:
        fb_safe.click()
        page.wait_for_timeout(4000)
        s1, st1 = fb_stats()
        print("feedback stats after click:", s1, json.dumps(st1)[:160] if st1 else None)
        body = page.evaluate("() => document.body.innerText")
        print("confirmation_shown:", "feedback" in body.lower() or "thank" in body.lower() or "saved" in body.lower())
    browser.close()