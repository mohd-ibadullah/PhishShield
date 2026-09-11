"""P6.1 durable store: history rows must survive a backend restart.

Same session cookie before/after restart; the row id scanned pre-restart must
still be returned by GET /api/history post-restart (R5 DB-backfill fix).
"""
import http.cookiejar
import json
import subprocess
import time
import urllib.request

BACK = "http://127.0.0.1:9212"
MARKER = "LIVE-QA-92-durable verify http://paypa1.example/durable"
BACKEND_DIR = r"C:\Users\froms\Desktop\2\backend"
PY = r"C:\Users\froms\Desktop\2\.venv\Scripts\python.exe"
LOG = r"C:\Users\froms\Desktop\2\diagnostics\gauntlet\p6_backend_restart_%s.log" % int(time.time())


def make_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def call(opener, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BACK + path, data=data,
                                 headers={"Content-Type": "application/json"}, method=method)
    try:
        with opener.open(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]


def backend_pid():
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if ":9212" in line and "LISTENING" in line:
            return line.split()[-1]
    return None


op, jar = make_opener()
st, scan = call(op, "POST", "/scan-email", {"email_text": MARKER})
print(f"scan: {st}")
st_h, hist = call(op, "GET", "/api/history")
rows = hist if isinstance(hist, list) else []
rid = rows[0].get("id") if rows else None
print(f"history before restart: n={len(rows)} id={rid}")
cookie = next((c for c in jar if c.name == "session" or "session" in c.name.lower()), None)
cookie_str = f"{cookie.name}={cookie.value}" if cookie else ""
print("session cookie captured:", bool(cookie_str))

pid = backend_pid()
print("killing backend pid:", pid)
subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=30)
time.sleep(2)

subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     f"Start-Process -FilePath '{PY}' -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','9212' "
     f"-WorkingDirectory '{BACKEND_DIR}' "
     f"-RedirectStandardOutput '{LOG}' -RedirectStandardError '{LOG}.err' -WindowStyle Hidden"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
)
healthy = False
deadline = time.time() + 150
while time.time() < deadline:
    try:
        with urllib.request.urlopen(BACK + "/health", timeout=5) as r:
            if r.status == 200:
                healthy = True
                break
    except Exception:
        pass
    time.sleep(3)
print("backend healthy after restart:", healthy)

# Re-open history with the SAME cookie (new opener but same cookie value).
op2 = urllib.request.build_opener()
req = urllib.request.Request(BACK + "/api/history", headers={"Cookie": cookie_str})
try:
    with op2.open(req, timeout=30) as r:
        hist2 = json.loads(r.read().decode())
    ids2 = [x.get("id") for x in hist2] if isinstance(hist2, list) else []
    print(f"history after restart: n={len(ids2)} id_present={rid in ids2}")
except urllib.error.HTTPError as e:
    print("history after restart: HTTP", e.code, e.read().decode("utf-8", "replace")[:100])