import pathlib
from playwright.sync_api import sync_playwright

FRONTEND = "http://127.0.0.1:5173"

eml = pathlib.Path("_test_probe.eml")
eml.write_text(
    "From: CFO Office <user8@example.invalid>\n"
    "Subject: Confidential: release urgent vendor transfer today\n"
    "\n"
    "Hi, I need you to urgently process a vendor bank transfer today. "
    "Keep this confidential and do not call back until it is done. "
    "Review the attached invoice and send confirmation once the payment is released.\n",
    encoding="utf-8",
)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(FRONTEND, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    page.get_by_text("upload file", exact=True).click()
    page.wait_for_timeout(1000)
    has_input = page.locator('input[type="file"]').count()
    print("file input count:", has_input)
    page.locator('input[type="file"]').set_input_files(str(eml.resolve()))
    page.wait_for_timeout(1000)
    # check textarea got the file content (mode auto-switched to real)
    ta = page.evaluate('document.querySelector("textarea")?.value?.length || 0')
    print("textarea chars after upload:", ta)
    # click Scan Email if not auto-triggered
    page.get_by_text("Scan Email", exact=True).click()
    page.wait_for_timeout(25000)
    body = page.evaluate("document.body.innerText")
    i = body.find("FINAL VERDICT")
    print("UPLOAD SCAN RESULT:", body[i:i + 300].replace("\n", " | ") if i >= 0 else "NO VERDICT")
    browser.close()
