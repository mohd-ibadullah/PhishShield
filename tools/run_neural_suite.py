import json
import uuid
import time
import requests

API_URL = "http://127.0.0.1:8000/scan-email"

TEST_CASES = [
    # GROUP A — 8 legitimate emails (must be Safe, score <= 25)
    {
        "id": "A1",
        "group": "Group A (Legitimate)",
        "name": "Bank statement (SBI)",
        "expected": "Safe",
        "text": """From: noreply@sbi.co.in
Subject: Your monthly account statement is ready

Dear Customer,
Your SBI account statement for July 2026 is now available in the net banking portal.
No action is required from your end. You can view or download it under "e-Statement".
Regards, State Bank of India"""
    },
    {
        "id": "A2",
        "group": "Group A (Legitimate)",
        "name": "OTP safety advisory (ICICI)",
        "expected": "Safe",
        "text": """From: alerts@icicibank.com
Subject: Reminder: we never ask for your OTP

Hello,
Please remember that ICICI Bank will never ask for your OTP, PIN or password over
call, SMS or email. If anyone asks for it, hang up and report on our website.
Team ICICI Bank"""
    },
    {
        "id": "A3",
        "group": "Group A (Legitimate)",
        "name": "Netflix receipt",
        "expected": "Safe",
        "text": """From: info@account.netflix.com
Subject: Your Netflix payment was received

Hi, we received your payment of Rs 649 for the Standard plan. Your next billing date
is 28 September 2026. No further action is needed. This is an automated message."""
    },
    {
        "id": "A4",
        "group": "Group A (Legitimate)",
        "name": "Office meeting (Sprint review)",
        "expected": "Safe",
        "text": """From: priya.mehta@company.in
Subject: Sprint review — Thursday 3 PM

Hi team, moving Thursday's sprint review to 3 PM so the QA demo fits. Agenda is in
the shared doc. Bring laptop. If that time is bad for you, reply here.
Priya"""
    },
    {
        "id": "A5",
        "group": "Group A (Legitimate)",
        "name": "HR policy update (verify payroll)",
        "expected": "Safe",
        "text": """From: hr@company.in
Subject: Action needed: verify your bank details for September payroll
Dear employee, for the September payroll run, please verify that the salary account
in the HR portal is correct. Log in to the portal — the link is the same one you use
every month — and confirm by 5 September. If already done, ignore this. Thanks, HR"""
    },
    {
        "id": "A6",
        "group": "Group A (Legitimate)",
        "name": "Password expiry from IT",
        "expected": "Safe",
        "text": """From: it-support@company.in
Subject: Your password expires in 7 days

Hi, your domain password expires on 04-Sep-2026. Change it at the usual self-service
page before then to avoid account lockout. No one from IT will ever ask for your
current password. — Infrastructure Team"""
    },
    {
        "id": "A7",
        "group": "Group A (Legitimate)",
        "name": "UPI credit alert (GPay)",
        "expected": "Safe",
        "text": """From: Google Pay
Subject: Rs 2,500 credited
You have received Rs 2,500 from rahul@okhdfcbank for "Dinner split".
Transaction id: 745628930012. No action needed."""
    },
    {
        "id": "A8",
        "group": "Group A (Legitimate)",
        "name": "IRCTC confirmed ticket",
        "expected": "Safe",
        "text": """From: irctcconnect@irctc.co.in
Subject: PNR 4821903657 — Chart prepared
Dear passenger, chart for train 12713 Visakhapatnam–Secunderabad on 02-Sep-2026 has
been prepared. Berth no. 34, Coach B2. Carry your ID proof. — IRCTC"""
    },

    # GROUP B — 6 real attacks (must be High Risk)
    {
        "id": "B1",
        "group": "Group B (Attacks)",
        "name": "SBI Account freeze + OTP scam",
        "expected": "High Risk",
        "text": """From: "SBI Secure" <sbi-alert@secure-bank-verify.xyz>
Subject: Aapka account block ho jayega
Dear customer, your account has been frozen. Share your OTP with our executive within
30 minutes to unblock. Call 98222XXXXX now."""
    },
    {
        "id": "B2",
        "group": "Group B (Attacks)",
        "name": "KYC Aadhaar-PAN link + phishing URL",
        "expected": "High Risk",
        "text": """From: KYC Update <kyc@pan-card-update.top>
Subject: Aadhaar-PAN linking pending — final notice
Update your KYC today or your account will be permanently closed. Click
http://pan-update.secure-login.click and enter your card details."""
    },
    {
        "id": "B3",
        "group": "Group B (Attacks)",
        "name": "Paytm Reward scam + OTP/UPI lure",
        "expected": "High Risk",
        "text": """From: Paytm Rewards <rewards@paytm-gift.icu>
Subject: Congratulations! You won Rs 50,000
You are our lucky user of the month. Claim now before midnight:
http://paytm-gift.icu/claim — share your UPI ID and the 6-digit code sent to you."""
    },
    {
        "id": "B4",
        "group": "Group B (Attacks)",
        "name": "Vendor payment / BEC (no URLs)",
        "expected": "High Risk",
        "text": """From: accounts@sunriselogistics-in.com
Subject: Updated bank details for this month's payment
Hi, our finance team has changed the beneficiary account. Please process the pending
invoice to the new A/C number 50100XXXXXX88, IFSC SUNB0001234, instead of the old
one. Payment is urgent, vendor meeting is blocked until then. Do not call to verify,
email reply is enough. — Accounts"""
    },
    {
        "id": "B5",
        "group": "Group B (Attacks)",
        "name": "Google Security Reply-To spoof + lure",
        "expected": "High Risk",
        "text": """From: Google Security <google@gmail.com>
Reply-To: recovery@mail-verify-support.xyz
Return-Path: bounce@198.51.100.7
Subject: Unusual sign-in from Hyderabad
We blocked a sign-in from Windows/Linux. If this was not you, use the recovery form
below within 24 hours or your account and all data will be deleted.
http://accounts.google.com-login.verify-now.click/recovery"""
    },
    {
        "id": "B6",
        "group": "Group B (Attacks)",
        "name": "Telugu Bank Account phishing",
        "expected": "High Risk",
        "text": """From: bank-update@alert-security.xyz
Subject: ఖాతా ధృవీకరణ అవసరం
మీ బ్యాంక్ ఖాతా నిలిపివేయబడుతోంది. వెంటనే ఈ లింక్లో వివరాలు నమోదు చేయండి:
http://bank-verify.secure-update.click — OTP ఎవరికీ ఇవ్వవద్దు."""
    },

    # GROUP C — 4 benign Indic emails (fairness check: must be Safe)
    {
        "id": "C1",
        "group": "Group C (Benign Indic)",
        "name": "Hindi GST report info",
        "expected": "Safe",
        "text": """From: newsalert@hindustan-times.com
Subject: GST नियमों में बदलाव — जुलाई रिपोर्ट
ग्राहकों के लिए जुलाई की GST रिपोर्ट पोर्टल पर उपलब्ध है। कोई कार्रवाई ज़रूरी नहीं है।"""
    },
    {
        "id": "C2",
        "group": "Group C (Benign Indic)",
        "name": "Hindi Airtel bill transactional",
        "expected": "Safe",
        "text": """From: care@airtel.in
Subject: आपका बिल तैयार है
आपका अगस्त बिल 1,299 रु. है। भुगतान 25 अगस्त तक आपके लिंक किए खाते से स्वतः हो जाएगा।"""
    },
    {
        "id": "C3",
        "group": "Group C (Benign Indic)",
        "name": "Telugu Electricity bill notification",
        "expected": "Safe",
        "text": """From: notifications@ts-southern.in
Subject: విద్యుత్ బిల్లు తెలుసుకోండి
మీ జూలై విద్యుత్ బిల్లు ₹1,842. ఈ నెల 20న ముందే చెల్లింపు జరుగుతుంది. మరింత సమాచారానికి
అప్లికేషన్ చూడండి."""
    },
    {
        "id": "C4",
        "group": "Group C (Benign Indic)",
        "name": "Telugu Andhra Bank meter reading",
        "expected": "Safe",
        "text": """From: alerts@andhrabank.in
Subject: మీటర్ రీడింగ్ నిర్ధారణ
మీ కనెక్షన్కు సంబంధించిన రీడింగ్ స్వీకరించబడింది. ఏమీ చేయాల్సిన అవసరం లేదు."""
    },

    # GROUP D — 3 paraphrase attacks (no banned keywords)
    {
        "id": "D1",
        "group": "Group D (Paraphrase)",
        "name": "Transfer money favor before flight",
        "expected": "Flagged",
        "text": """From: amita.rao@internal-mail-hub.com
Subject: Small favour before I leave
Could you move ₹45,000 to the number in the attached note today? My banking app is
acting up and the transfer has to go before I fly out at 9. Don't want to worry you
over the phone."""
    },
    {
        "id": "D2",
        "group": "Group D (Paraphrase)",
        "name": "One-time sign-in refresh link + 6 digits",
        "expected": "Flagged",
        "text": """From: it-desk@company-mail-support.com
Subject: One-time sign-in refresh
A new device was added to your profile yesterday, so sign in once from the settings
page I linked in last week's note and confirm the six digits it shows you. That's all
it needs — the old session keeps working till Friday."""
    },
    {
        "id": "D3",
        "group": "Group D (Paraphrase)",
        "name": "Landlord changed account PDF lure",
        "expected": "Flagged",
        "text": """From: "Ramesh (Landlord)" <ramesh.naresh@gmail.com>
Subject: rent this month
Nope not the usual account this month, owner asked me to collect. Send to the number
in the PDF, I'll confirm once received. Thanks!"""
    },
]

results = []

for case in TEST_CASES:
    for attempt in range(5):
        try:
            sess_id = f"test_{case['id']}_{uuid.uuid4().hex[:6]}"
            res = requests.post(API_URL, json={"email_text": case["text"], "session_id": sess_id}, timeout=15)
            if res.status_code == 429:
                time.sleep(1.0)
                continue
            data = res.json()
            score = data.get("risk_score")
            verdict = data.get("verdict")
            ml_prob = data.get("ml_probability")
            model_used = data.get("model_used")
            signals = data.get("signals") or data.get("matched_signals") or []
            
            passed = False
            if case["group"].startswith("Group A"):
                passed = (verdict == "Safe" and score <= 25)
            elif case["group"].startswith("Group B"):
                passed = (verdict == "High Risk")
            elif case["group"].startswith("Group C"):
                passed = (verdict == "Safe")
            elif case["group"].startswith("Group D"):
                passed = (verdict in ["Suspicious", "High Risk"])
                
            results.append({
                "id": case["id"],
                "group": case["group"],
                "name": case["name"],
                "expected": case["expected"],
                "score": score,
                "verdict": verdict,
                "ml_prob": round(float(ml_prob or 0.0), 4),
                "model_used": model_used,
                "passed": passed,
                "signals": signals,
            })
            time.sleep(0.3)
            break
        except Exception as e:
            time.sleep(0.5)

with open("backend/reports/neural_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\n| ID | Test Case | Expected | Score | Verdict | ML Prob | Model Used | Status |")
print("|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|")
for r in results:
    status = "PASS" if r["passed"] else "FAIL"
    print(f"| {r['id']} | {r['name']} | {r['expected']} | {r['score']} | {r['verdict']} | {r['ml_prob']} | {r['model_used']} | {status} |")
