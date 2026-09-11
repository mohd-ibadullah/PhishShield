"""P4.4 backend-restart live-indicator check (robust version).

Kill backend -> indicator flips to Offline (frontend refreshes health on a 60s
cycle). Scan while down degrades gracefully. Restart backend -> indicator flips
back to Connected. Timestamps per transition. Never blocks: backend restart is
a detached `cmd start /b`, health is a socket-level connect check.
"""
import faulthandler
import socket
import subprocess
import time
from datetime import datetime, timezone

faulthandler.enable()
faulthandler.dump_traceback_later(40, repeat=True)

from playwright.sync_api import sync_playwright

FRONT = "http://127.0.0.1:4173"
BACK = "http://127.0.0.1:9212"
BACKEND_DIR = r"C:\Users\froms\Desktop\2\backend"
PY = r"C:\Users\froms\Desktop\2\.venv\Scripts\python.exe"
LOG = r"C:\Users\froms\Desktop\2\diagnostics\gauntlet\p4_backend_restart_%s.log" % int(time.time())


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def backend_pid() -> str | None:
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if ":9212" in line and "LISTENING" in line:
            return line.split()[-1]
    return None


def health_ok(timeout_s: int = 4) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 9212), timeout=timeout_s) as s:
            s.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            data = s.recv(64)
            return b"200" in data
    except Exception:
        return False


def indicator(page) -> str:
    el = page.locator("text=/Backend:/i").first
    return el.inner_text()[:60] if el.count() else "no-indicator-element"


def poll_indicator(page, want: str, timeout_s: int) -> tuple[str, str]:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        last = indicator(page)
        if want in last:
            return last, now()
        page.wait_for_timeout(1500)
    return last, now()


def restart_backend() -> None:
    # PowerShell Start-Process with a UNIQUE log file per restart (a previous
    # backend may still hold an old file open, which blocks the redirect).
    # No capture_output: the started backend inherits PowerShell's stdout/stderr
    # handles, so communicate() would wait for pipe EOF that never comes. The
    # backend's real logs go to LOG via -RedirectStandardOutput.
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process -FilePath '{PY}' -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','9212' "
         f"-WorkingDirectory '{BACKEND_DIR}' "
         f"-RedirectStandardOutput '{LOG}' -RedirectStandardError '{LOG}.err' -WindowStyle Hidden"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )


def main() -> None:
    dialogs: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.on("dialog", lambda d: (dialogs.append(d.message[:60]), d.dismiss()))

        page.goto(FRONT + "/", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(2500)
        print(f"T0 {now()} initial indicator: {indicator(page)}")

        pid = backend_pid()
        print(f"backend pid on 9212: {pid}")
        if not pid:
            print("BLOCKED: no backend listening on 9212; aborting")
            return

        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=30)
        print(f"T1 {now()} taskkill /F /PID {pid} issued")

        flipped, t2 = poll_indicator(page, "Offline", timeout_s=90)
        print(f"T2 {t2} indicator after kill: {flipped}")

        try:
            ta = page.locator("textarea").first
            ta.fill("LIVE-QA-81 submit-while-down probe")
            page.locator('button:has-text("Scan Email")').first.click()
            page.wait_for_timeout(6000)
            body = page.evaluate("() => document.body.innerText")
            print(f"submit-while-down: body_len={len(body)} crash={'Traceback' in body} dialogs={len(dialogs)}")
        except Exception as exc:
            print(f"submit-while-down: EXCEPTION {type(exc).__name__}: {str(exc)[:80]}")

        print(f"T3a {now()} issuing backend restart -> {LOG}")
        restart_backend()
        print(f"T3b {now()} restart subprocess returned")

        healthy = False
        deadline = time.time() + 150
        while time.time() < deadline and not health_ok():
            time.sleep(3)
        healthy = health_ok()
        print(f"health after restart: {healthy} at {now()} (pid {backend_pid()})")

        back, t4 = poll_indicator(page, "Connected", timeout_s=90)
        print(f"T4 {t4} indicator after restart: {back}")
        print(f"dialogs_fired={len(dialogs)}")
        browser.close()


if __name__ == "__main__":
    main()