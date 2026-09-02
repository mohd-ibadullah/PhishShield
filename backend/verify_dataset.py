import requests

API_URL = "http://localhost:8000/api/analyze"

safe_base = [
    {"text": "Your Amazon order #12345 has been successfully processed and shipped. Track it here: https://amazon.in/orders", "headers": "From: user1@example.invalid\nReturn-Path: user2@example.invalid"},
    {"text": "Security alert: We detected a new login from a Windows device. If this was you, you can safely ignore this. Google Accounts.", "headers": "From: user3@example.invalid\nReturn-Path: user4@example.invalid"},
    {"text": "Your monthly LinkedIn digest is here. See who viewed your profile at linkedin.com.", "headers": "From: user5@example.invalid\nReturn-Path: user6@example.invalid"},
    {"text": "Notification: Your Microsoft subscription has been renewed.", "headers": "From: user7@example.invalid\nReturn-Path: user8@example.invalid"},
    {"text": "Thank you for shopping snippet. Your transaction ID is 9982. Expected delivery tomorrow.", "headers": "From: user9@example.invalid\nReturn-Path: user10@example.invalid"},
]
phish_base = [
    {"text": "Transfer money now!", "headers": "From: user11@example.invalid"},
    {"text": "Update KYC immediately to avoid suspension.", "headers": "From: user12@example.invalid"},
    {"text": "Send OTP urgently.", "headers": "From: user13@example.invalid"},
    {"text": "Verify account now.", "headers": "From: user14@example.invalid"},
    {"text": "Hello Finance Team, please open the attached confidential invoice and process wire transfer immediately.", "headers": "From: user15@example.invalid\nReturn-Path: user16@example.invalid"},
]
mixed_base = [
    {"text": "Your Amazon order has shipped. However, you've won a free prize! Claim reward here: http://sketchyclaim.ru/winner", "headers": "From: user17@example.invalid\nReturn-Path: user18@example.invalid"},
    {"text": "Google Account Notice: We blocked a login. Also click here for a $500 gift card http://scam.gift/reward", "headers": "From: user19@example.invalid\nReturn-Path: user20@example.invalid"},
    {"text": "Thank you for shopping. For a 100% cashback offer, submit your card details urgently.", "headers": "From: user21@example.invalid"},
    {"text": "Microsoft alert: verify your account. Plus download this free attached PDF for a bonus.", "headers": "From: user22@example.invalid"},
    {"text": "Your LinkedIn digest! Urgent: update your credentials immediately using this link.", "headers": "From: user23@example.invalid"},
]
hinglish_base = [
    {"text": "Aapka account block ho jayega! Turant apna OTP bhejo warna service band.", "headers": "From: user24@example.invalid"},
    {"text": "Jaldi se apna PAN number update karo, warna kal se account suspended.", "headers": "From: user25@example.invalid"},
    {"text": "Sirji, prize claim karne ke liye link par click karein aur OTP share karein.", "headers": "From: user26@example.invalid"},
    {"text": "Turant apna KYC details verify karo idhar click karke.", "headers": "From: user27@example.invalid"},
    {"text": "Free cashback mila hai, abhi verify karo ya timeout ho jayega.", "headers": "From: user28@example.invalid"},
]

dataset = []
for i in range(25):
    s = safe_base[i % len(safe_base)].copy(); s["expected"] = "SAFE"; s["text"] += f" [ID:{i}]"; dataset.append(s)
    p = phish_base[i % len(phish_base)].copy(); p["expected"] = "PHISHING"; p["text"] += f" [ID:{i}]"; dataset.append(p)
    m = mixed_base[i % len(mixed_base)].copy(); m["expected"] = "PHISHING"; m["text"] += f" [ID:{i}]"; dataset.append(m)
    h = hinglish_base[i % len(hinglish_base)].copy(); h["expected"] = "PHISHING"; h["text"] += f" [ID:{i}]"; dataset.append(h)

total = len(dataset)
fps = 0
fns = 0
correct = 0

print(f"Starting test for {total} emails...", flush=True)

import concurrent.futures
def test_email(item):
    payload = {"emailText": item["text"], "headers": item["headers"]}
    try:
        response = requests.post(API_URL, json=payload, timeout=20)
        if response.status_code == 200:
            data = response.json()
            score = data.get("riskScore", 0)
            verdict = "PHISHING" if score > 25 else "SAFE"
            return item, verdict, score
        return item, "ERROR", 0
    except Exception:
        return item, "ERROR", 0

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(test_email, dataset)

for item, verdict, score in results:
    if verdict == item["expected"]:
        correct += 1
    elif verdict == "ERROR":
        pass
    else:
        if verdict == "PHISHING":
            fps += 1
            print(f"FALSE POSITIVE: {item['text'][:50]}... Score: {score}")
        else:
            fns += 1
            print(f"FALSE NEGATIVE: {item['text'][:50]}... Score: {score}")

print("--------------------------------------------------")
print(f"TOTAL TESTED: {total}")
print(f"ACCURACY: {(correct / total) * 100:.2f}%")
print(f"FALSE POSITIVES: {fps} ({(fps / total) * 100:.2f}%)")
print(f"FALSE NEGATIVES: {fns} ({(fns / total) * 100:.2f}%)")
print("--------------------------------------------------")
