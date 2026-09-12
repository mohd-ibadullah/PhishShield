import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_path = "backend/models/securebert_model"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

s1 = "Your monthly account statement for July is now available in net banking."
s2 = "Your SBI account statement for July 2026 is now available in the net banking portal."

words = ["Your", "monthly", "account", "statement", "for", "July", "is", "now", "available", "in", "net", "banking", "portal", "SBI", "Dear", "Customer", "Regards"]

print("=== Logits of Incremental Additions ===")
cur = ""
for w in s2.split():
    cur = (cur + " " + w).strip()
    inputs = tokenizer(cur, return_tensors="pt")
    with torch.no_grad():
        out = model(**inputs)
        logits = out.logits[0].tolist()
        probs = torch.softmax(out.logits, dim=-1)[0].tolist()
    print(f"'{cur}'\n  -> Logits: [{logits[0]:.2f}, {logits[1]:.2f}] | Phish Prob={probs[1]:.4f}")
