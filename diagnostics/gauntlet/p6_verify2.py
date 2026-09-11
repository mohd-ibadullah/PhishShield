"""P6.1 pass 2: /api/report with a real scan_id, /api/feedback/export, and the
durable-store check (history rows survive a backend restart)."""
import http.cookiejar
import json
import subprocess
import time
import urllib.request

BACK = "http://127.0.0.1:9212"
MARKER = "LIVE-QA-91-p6b verify http://paypa1.example/p6b"


def make_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


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


op = make_opener()
st, scan = call(op, "POST", "/scan-email", {"email_text": MARKER})
print(f"scan: {st}")
sid = (scan or {}).get("scan_id") or (scan or {}).get("id")
print("scan_id:", sid)
st_h, hist = call(op, "GET", "/api/history")
rows = hist if isinstance(hist, list) else []
print(f"history: {st_h} n={len(rows)}")
row = rows[0] if rows else None
if row:
    print("row: ts=%r classification=%r verdict=%r emailPreview=%r" % (
        row.get("timestamp"), row.get("classification"), row.get("verdict"), row.get("emailPreview")))
    print("durable_row_id:", row.get("id"))
    # report with the REAL scan id
    r_st, r_body = call(op, "POST", "/api/report", {"scan_id": row.get("id")})
    print(f"/api/report(real id): {r_st} body={str(r_body)[:80]}")
f_st, f_body = call(op, "GET", "/api/feedback/export")
print(f"/api/feedback/export: {f_st}")
ids_before = {r.get("id") for r in rows}
print("ids_before_restart:", len(ids_before), sorted(ids_before)[:3])
with open(r"C:\Users\froms\Desktop\2\diagnostics\gauntlet\p6_ids_before.json", "w") as fh:
    json.dump(sorted(ids_before), fh)
print("DONE")