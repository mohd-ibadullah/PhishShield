import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_path = "backend/models/securebert_model"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

A1_TEXT = """From: noreply@sbi.co.in
Subject: Your monthly account statement is ready

Dear Customer,
Your SBI account statement for July 2026 is now available in the net banking portal.
No action is required from your end. You can view or download it under "e-Statement".
Regards, State Bank of India"""

phrases = [
    ("Full A1", A1_TEXT),
    ("1. Remove 'net banking portal'", A1_TEXT.replace("net banking portal", "portal")),
    ("2. Remove 'SBI' + 'State Bank of India'", A1_TEXT.replace("SBI", "ABC").replace("State Bank of India", "ABC Corp")),
    ("3. Remove 'e-Statement'", A1_TEXT.replace('"e-Statement"', 'portal')),
    ("4. Remove 'account statement'", A1_TEXT.replace("account statement", "summary document")),
    ("5. Pure 'account statement' alone", "Your account statement is ready"),
    ("6. Pure 'net banking portal' alone", "available in the net banking portal"),
    ("7. Pure 'SBI' alone", "State Bank of India SBI"),
    ("8. Pure 'No action required' alone", "No action is required from your end."),
    ("9. Bank + e-Statement + portal", "SBI account statement net banking portal e-Statement"),
]

print(f"{'Text Variation':<40} | {'Prob[0] (Safe)':<14} | {'Prob[1] (Phish)':<14}")
print("-" * 75)
for label, p in phrases:
    inputs = tokenizer(p, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        out = model(**inputs)
        probs = torch.softmax(out.logits, dim=-1)[0].tolist()
    print(f"{label:<40} | {probs[0]:<14.4f} | {probs[1]:<14.4f}")
