"""Capture network traffic around the 'Mark as Safe' feedback click."""
import time

from playwright.sync_api import sync_playwright

FRONT = "http://127.0.0.1:4173"
MARKER = "LIVE-QA-94-fbnet verify http://paypa1.example/fbnet"

reqs: list[str] = []
resps: list[tuple[str, int]] = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.on("request", lambda r: reqs.append(f"{r.method} {r.url}") if "feedback" in r.url else None)
    page.on("response", lambda r: resps.append((r.url, r.status)) if "feedback" in r.url else None)
    page.on("console", lambda m: print("CONSOLE:", m.text[:150]) if m.type == "error" else None)

    page.goto(FRONT + "/", wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(1500)
    ta = page.locator("textarea").first
    ta.fill(MARKER)
    page.locator('button:has-text("Scan Email")').first.click()
    page.wait_for_timeout(12000)
    fb = page.locator('button:has-text("Mark as Safe")')
    print("mark_as_safe_count:", fb.count())
    if fb.count():
        fb.first.click()
        page.wait_for_timeout(5000)
    print("feedback_requests:", reqs)
    print("feedback_responses:", resps)
    body = page.evaluate("() => document.body.innerText")
    print("shows_failure:", "Could not save" in body)
    print("shows_success:", "Feedback saved" in body or "Thanks! Model will improve" in body)
    browser.close()