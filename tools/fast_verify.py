import os
import json
import re

print("=== 1. History & Privacy ===")
# Check recent-scans / history in main.py
with open("backend/main.py", "r", encoding="utf-8") as f:
    main_py = f.read()

for ep in ["/recent-scans", "/api/history", "/scans", "/feedback", "/retrain", "/internal"]:
    matches = [line.strip() for line in main_py.splitlines() if f'"{ep}' in line and "@app." in line]
    print(f"Endpoint {ep}: {matches}")

print("\n=== 2. id2label in SecureBERT ===")
if os.path.exists("backend/models/securebert_model/config.json"):
    with open("backend/models/securebert_model/config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
        print("SecureBERT id2label:", cfg.get("id2label"))
        print("SecureBERT label2id:", cfg.get("label2id"))

print("\n=== 3. False Positive Rate Formula ===")
# Check frontend dashboard where FPR is computed
with open("frontend/artifacts/phishshield/src/pages/dashboard.tsx", "r", encoding="utf-8") as f:
    dash = f.read()
for i, line in enumerate(dash.splitlines()):
    if "False Positive Rate" in line or "falsePositive" in line or "1 - precision" in line or "1 - (" in line or "5.9%" in line:
        print(f"dashboard.tsx:{i+1}: {line.strip()[:100]}")

print("\n=== 4. Training Meta Files & License ===")
print("Root LICENSE exists:", os.path.exists("LICENSE"))
print("data/training_meta.json exists:", os.path.exists("data/training_meta.json"))
print("backend/data/training_meta.json exists:", os.path.exists("backend/data/training_meta.json"))

print("\n=== 5. Dataset rows ===")
if os.path.exists("data/Phishing_Email.csv"):
    with open("data/Phishing_Email.csv", "r", encoding="utf-8") as f:
        print("data/Phishing_Email.csv lines:", len(f.readlines()))
if os.path.exists("data/Phishing_Email_cleaned.csv"):
    with open("data/Phishing_Email_cleaned.csv", "r", encoding="utf-8") as f:
        print("data/Phishing_Email_cleaned.csv lines:", len(f.readlines()))

