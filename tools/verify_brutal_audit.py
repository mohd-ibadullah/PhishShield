import os
import re
import json
import requests
import glob

evidence = {}

# 1. Check /api/history and /recent-scans authentication & raw previews
with open("backend/main.py", "r", encoding="utf-8") as f:
    main_code = f.read()

has_auth_history = bool(re.search(r'@app\.(?:get|post)\(["\']/(?:recent-scans|api/history|history)', main_code))
evidence["issue_1_endpoints"] = []
for line in main_code.splitlines():
    if "/recent-scans" in line or "/history" in line:
        evidence["issue_1_endpoints"].append(line.strip())

# 2. Check /api/feedback, /api/retrain, /internal endpoints auth
evidence["issue_2_endpoints"] = []
for line in main_code.splitlines():
    if any(ep in line for ep in ["/retrain", "/feedback", "/internal/", "/debug"]):
        if "@app." in line:
            evidence["issue_2_endpoints"].append(line.strip())

# 3. Check id2label in models/securebert_model/config.json and indicbert_model
evidence["id2label"] = {}
if os.path.exists("backend/models/securebert_model/config.json"):
    with open("backend/models/securebert_model/config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
        evidence["id2label"]["securebert"] = cfg.get("id2label")

# 4. Check formula for false positive rate
evidence["fpr_formula"] = []
for fpath in glob.glob("frontend/artifacts/**/*.ts*", recursive=True) + glob.glob("backend/**/*.py", recursive=True):
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if "false_positive_rate" in line or "falsePositiveRate" in line or "1 - precision" in line or "1 - (precision" in line:
                    evidence["fpr_formula"].append(f"{fpath}:{idx+1}: {line.strip()}")
    except Exception:
        pass

# 5. Check LICENSE, 2 training_meta files, 2000 rows
evidence["license_exists"] = os.path.exists("LICENSE")
evidence["data_meta"] = os.path.exists("data/training_meta.json")
evidence["backend_data_meta"] = os.path.exists("backend/data/training_meta.json")

print(json.dumps(evidence, indent=2))
