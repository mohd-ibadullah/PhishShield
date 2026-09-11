"""P6.1 live verification against http://127.0.0.1:9212 (real backend).

Checks the owner-decided BLOCKED list:
1. /api/history durable store (rows survive backend restart)
2. timestamp never serialises as "None"
3. classification labels consistent between scan response and history row
4. /api/report + /api/feedback/export implemented
5. emailPreview policy stated in the row payload
6. feedback control surfaced in the UI (checked separately via Playwright)
"""
import http.cookiejar
import json
import time
import urllib.request

BACK = "http://127.0.0.1:9212"
MARKER = "LIVE-QA-90-p6 verify http://paypa1.example/p6"


def make_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def post(opener, path, body):
    req = urllib.request.Request(BACK + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with opener.open(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw[:120]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:120]


def get(opener, path):
    try:
        with opener.open(BACK + path, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw[:120]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:120]


op = make_opener()
# 1. scan -> session cookie + history row
st, scan = post(op, "/scan-email", {"email_text": MARKER})
print(f"scan-email: {st}")
hist_st, hist = get(op, "/api/history")
row = hist[0] if isinstance(hist, list) and hist else None
print(f"history: {hist_st} n={len(hist) if isinstance(hist, list) else '?'}")
if row:
    print("row: id=%s ts=%r classification=%r verdict=%r riskScore=%r emailPreview=%r" % (
        row.get("id"), row.get("timestamp"), row.get("classification"),
        row.get("verdict"), row.get("riskScore"), row.get("emailPreview")))
    print("timestamp_is_none:", row.get("timestamp") is None or row.get("timestamp") == "None")
    # classification consistency: history classification vs scan response verdict
    sv = (scan or {}).get("verdict")
    sc = (scan or {}).get("classification") or (scan or {}).get("verdict_binary")
    print("scan_response: verdict=%r classification=%r" % (sv, sc))
    print("emailPreview_policy_redacted:", isinstance(row.get("emailPreview"), str)
          and row.get("emailPreview", "").startswith(row.get("id", "")[:8]) and "..." in row.get("emailPreview", ""))
# 2. /api/report
r_st, r_body = post(op, "/api/report", {"scan_id": row.get("id") if row else "x"})
print(f"/api/report: {r_st}")
# 3. /api/feedback/export
f_st, f_body = get(op, "/api/feedback/export")
print(f"/api/feedback/export: {f_st}")
# 4. /api/history durable: rows before restart (id set)
ids_before = {r.get("id") for r in hist} if isinstance(hist, list) else set()
print("ids_before_restart:", len(ids_before))
with open(r"C:\Users\froms\Desktop\2\diagnostics\gauntlet\p6_ids_before.json", "w") as fh:
    json.dump(sorted(ids_before), fh)
print("DONE")