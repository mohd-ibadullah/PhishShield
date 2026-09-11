import hashlib, json, sys, time
import urllib.request

BASE = "http://127.0.0.1:9212"

PROBES = [
    ("G-HI-01", "HI", "Subject: LIVE-QA-1\nFrom: user1@example.invalid\n\nआपका KYC अपडेट नहीं हुआ। UPI बंद होने से पहले अपना पासवर्ड दर्ज करें।", "PHISH"),
    ("G-TE-01", "TE", "Subject: LIVE-QA-2\nFrom: user2@example.invalid\n\nమీ ఖాతా వేలిముద్ర కాలిపోతోంది. వెంటనే నగదు బదిలీ చేయండి: http://sbi-secure.example/login", "PHISH"),
    ("G-EN-01", "EN", "Subject: LIVE-QA-3\nFrom: user3@example.invalid\n\nVerify your account immediately: http://paypa1.example/verify or lose access.", "PHISH"),
    ("G-EN-02", "EN", "Subject: LIVE-QA-4\nFrom: user4@example.invalid\n\nYour Amazon order #402-8837291 has shipped. Expected delivery: Friday. Track at example.invalid/track.", "HAM"),
    ("G-UR-01", "UR", "Subject: LIVE-QA-5\nFrom: user5@example.invalid\n\nآپ کا اکاؤنٹ معطل کر دیا گیا ہے۔ فوری تصدیق کریں: http://urdu-verify.example/login", "PHISH"),
    ("G-TA-01", "TA", "Subject: LIVE-QA-6\nFrom: user6@example.invalid\n\nஉங்கள் கணக்கு இன்று மூடப்படும். உடனே சரிபார்க்கவும்: http://tamil-secure.example/login", "PHISH"),
    ("G-BN-01", "BN", "Subject: LIVE-QA-7\nFrom: user7@example.invalid\n\nআপনার অ্যাকাউন্ট আজ বন্ধ হয়ে যাবে। এখনই যাচাই করুন: http://bengali-verify.example/login", "PHISH"),
    ("G-MX-01", "MX", "Subject: LIVE-QA-8\nFrom: user8@example.invalid\n\nAapka account block ho gaya hai. Abhi OTP bhejo aur password daalo: http://hdfc-secure.example/login", "PHISH"),
    ("G-MKT-01", "MKT", "Subject: LIVE-QA-9 Unsubscribe anytime\nFrom: newsletter@example.invalid\n\nWeekly digest: top stories this week, plus a 20% discount code for subscribers. Unsubscribe here.", "HAM"),
]

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

rows = []
for pid, cat, text, expected in PROBES:
    body = json.dumps({"email_text": text}).encode()
    req = urllib.request.Request(BASE + "/scan-email", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with opener.open(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    ms = round((time.perf_counter() - t0) * 1000, 1)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rows.append({
        "id": pid, "category": cat, "expected": expected,
        "email_sha256": sha[:16],
        "risk_score": data.get("risk_score"),
        "verdict": data.get("verdict"),
        "router_leg": data.get("router_leg"),
        "detected_language": data.get("detectedLanguage") or data.get("language"),
        "ms": ms,
    })
    print(json.dumps(rows[-1], ensure_ascii=False))

with open("diagnostics/gauntlet/p2_scan_rows.json", "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1, ensure_ascii=False)
print("rows written:", len(rows))
