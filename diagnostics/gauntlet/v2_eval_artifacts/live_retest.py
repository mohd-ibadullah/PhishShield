"""Live re-test of the V2 XLM-R checkpoint (model_merged) against the committed eval claims.

Runs the exact model_merged weights on locally constructed probes across all three
classes plus modern-attack-style text, and compares with evaluation_results.json.
No thresholds are touched; raw argmax + probabilities are pasted.
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import logging

logging.disable(logging.CRITICAL)

import torch  # type: ignore
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore

MODEL_DIR = Path(__file__).resolve().parents[3] / "model_merged"

PROBES = [
    # (tag, expected_class, text)
    ("phish-classic", 0, "Dear Customer, your SBI account is suspended. Verify now at http://sbi-kyc-verify.xyz and share your OTP."),
    ("phish-otp", 0, "Your HDFC netbanking will be blocked today. Confirm your credentials immediately: http://hdfc-secure-alert.com"),
    ("spam-marketing", 1, "Congratulations! You won a FREE iPhone 17 lottery. Claim your prize now, limited offer, click here!"),
    ("spam-bulk", 1, "50% OFF MEGA SALE this weekend only! Buy now, free shipping on all orders over Rs.999. Unsubscribe here."),
    ("ham-normal", 2, "Hi, meeting at 3pm tomorrow in conference room B. Please bring the quarterly report."),
    ("ham-bank-legit", 2, "Your monthly account statement for August is now available in your inbox archive. No action is required."),
    # Modern-attack style (the weak spot per evaluation_results.json)
    ("modern-llm-phish", 0, "Hi Ananya, following up on the invoice dispute — the corrected payment portal is linked here. Please re-verify your banking credentials through the secure form so we can release the refund today. Kind regards, Billing Team."),
    ("modern-bec", 0, "Hey, I'm in a board meeting and can't take calls. I need you to process an urgent wire transfer to our new vendor. Reply with the account confirmation as soon as possible. — Director"),
]

tok = AutoTokenizer.from_pretrained(str(MODEL_DIR), local_files_only=True)
mdl = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR), local_files_only=True)
mdl.eval()

LABELS = {0: "phishing", 1: "spam", 2: "ham"}

print(f"model: {MODEL_DIR}")
print(f"{'tag':<18} {'expected':<10} {'argmax':<10} {'p0':<8} {'p1':<8} {'p2':<8} verdict-match")
print("-" * 78)
results = []
for tag, expected, text in PROBES:
    enc = tok(text, truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        probs = torch.softmax(mdl(**enc).logits, dim=-1)[0].tolist()
    argmax = int(max(range(len(probs)), key=lambda i: probs[i]))
    got = LABELS[argmax]
    exp = LABELS[expected]
    match = "YES" if argmax == expected else "NO"
    print(f"{tag:<18} {exp:<10} {got:<10} {probs[0]:<8.4f} {probs[1]:<8.4f} {probs[2]:<8.4f} {match}")
    results.append({"tag": tag, "expected": exp, "got": got, "match": argmax == expected, "probs": [round(p, 4) for p in probs]})

print()
n_match = sum(1 for r in results if r["match"])
print(f"matches: {n_match}/{len(results)}")
print()
print("=== modern-attack slices (from evaluation_results.json, for reference) ===")
print("cross_source_ood (CEAS-family): phishing recall = 0.0  |  curated_modern_dark: phishing recall = 0.03")
print("=> the zip's own eval already flagged: legacy-era model blind to modern phishing")
