import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_path = "backend/models/securebert_model"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

# Test cases with explicit length handling
cases = [
    ("Full A1 (with headers)", "From: noreply@sbi.co.in\nSubject: Your monthly account statement is ready\n\nDear Customer,\nYour SBI account statement for July 2026 is now available in the net banking portal.\nNo action is required from your end. You can view or download it under \"e-Statement\".\nRegards, State Bank of India"),
    ("Previous Safe 1 sentence", "Your monthly account statement for July is now available in net banking."),
    ("Pure 'account statement'", "account statement"),
    ("Pure 'net banking portal'", "net banking portal"),
    ("Pure 'SBI'", "SBI"),
    ("Pure 'Dear Customer'", "Dear Customer"),
    ("Pure 'Regards, State Bank of India'", "Regards, State Bank of India"),
    ("Control Safe (Meeting)", "Meeting scheduled tomorrow at 3 PM in conference room."),
    ("Control Phish (OTP urgent)", "Send OTP immediately or bank account will be blocked"),
]

print(f"{'Input Text':<45} | {'Logit[0]':<9} | {'Logit[1]':<9} | {'Softmax[0] (Safe)':<18} | {'Softmax[1] (Phish)':<18}")
print("-" * 110)

for label, text in cases:
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        out = model(**inputs)
        logits = out.logits[0].tolist()
        probs = torch.softmax(out.logits, dim=-1)[0].tolist()
    print(f"{label:<45} | {logits[0]:<9.4f} | {logits[1]:<9.4f} | {probs[0]:<18.4f} | {probs[1]:<18.4f}")
