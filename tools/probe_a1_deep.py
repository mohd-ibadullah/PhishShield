import hashlib
import json
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import requests
import sys

# Test A1 Text - exact byte-identical
A1_TEXT = """From: noreply@sbi.co.in
Subject: Your monthly account statement is ready

Dear Customer,
Your SBI account statement for July 2026 is now available in the net banking portal.
No action is required from your end. You can view or download it under "e-Statement".
Regards, State Bank of India"""

# 1. Check SHA256 of local model.safetensors
safetensors_path = "backend/models/securebert_model/model.safetensors"
h = hashlib.sha256()
with open(safetensors_path, "rb") as f:
    while chunk := f.read(8192 * 1024):
        h.update(chunk)
local_sha256 = h.hexdigest()
print(f"1. Local model.safetensors SHA256:\n   {local_sha256}")

# 2. Raw SecureBERT inference on A1 (raw string vs tokenization variations)
model_path = "backend/models/securebert_model"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

# Test raw A1
inputs_raw = tokenizer(A1_TEXT, return_tensors="pt", truncation=True, max_length=512)
with torch.no_grad():
    out_raw = model(**inputs_raw)
    probs_raw = torch.softmax(out_raw.logits, dim=-1)[0].tolist()

# Test A1 body only (without From / Subject)
body_only = A1_TEXT.split("\n\n", 1)[-1]
inputs_body = tokenizer(body_only, return_tensors="pt", truncation=True, max_length=512)
with torch.no_grad():
    out_body = model(**inputs_body)
    probs_body = torch.softmax(out_body.logits, dim=-1)[0].tolist()

print(f"\n2. Local RAW Model on A1:")
print(f"   Full A1 text Prob[0]={probs_raw[0]:.4f}, Prob[1]={probs_raw[1]:.4f}")
print(f"   Body-only text Prob[0]={probs_body[0]:.4f}, Prob[1]={probs_body[1]:.4f}")

# 3. Local Pipeline calculate_email_risk on A1
sys.path.insert(0, "backend")
from main import calculate_email_risk, compute_language_model_probability, clean_text

cleaned = clean_text(A1_TEXT)
pipe_prob, pipe_model = compute_language_model_probability(A1_TEXT, cleaned)
pipe_risk = calculate_email_risk(A1_TEXT)

print(f"\n3. Local Pipeline on A1:")
print(f"   compute_language_model_probability: {pipe_prob:.4f} (model={pipe_model})")
print(f"   calculate_email_risk: risk_score={pipe_risk.get('risk_score')}, ml_prob={pipe_risk.get('ml_probability')}")

# Token breakdown of A1
tokens = tokenizer.tokenize(A1_TEXT)
print(f"\n4. A1 Tokens (count={len(tokens)}):")
print(f"   First 20 tokens: {tokens[:20]}")
print(f"   SBI tokens: {tokenizer.tokenize('SBI')} | noreply@sbi.co.in: {tokenizer.tokenize('noreply@sbi.co.in')}")
