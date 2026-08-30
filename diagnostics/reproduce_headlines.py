"""Recompute committed TF-IDF headline measurements without writing artifacts."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "Phishing_Email.csv"
METADATA_PATH = ROOT / "data" / "training_meta.json"
EVAL_SET_PATH = Path(__file__).resolve().parent / "eval_set_v1.jsonl"
LABEL_MAP = {"Phishing Email": 1, "Safe Email": 0, "phishing": 1, "safe": 0}


def clean_text(text: str) -> str:
    text = str(text).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text)).strip()


def read_training_rows() -> tuple[list[str], list[int]]:
    # DictReader handles the committed CSV's quoted, multiline email bodies.
    with DATASET_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"email_text", "label"}.issubset(rows[0]):
        raise ValueError("Expected email_text and label columns")
    texts, labels = [], []
    for row in rows:
        text, label = row["email_text"], row["label"].strip().lower()
        if not text or label not in LABEL_MAP:
            raise ValueError(f"Invalid committed row label: {row['label']!r}")
        texts.append(clean_text(text))
        labels.append(LABEL_MAP[label])
    return texts, labels


def read_eval_count() -> int:
    with EVAL_SET_PATH.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip() and json.loads(line))


def main() -> None:
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    texts, labels = read_training_rows()
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    vectorizer = TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=2,
                                 stop_words="english", sublinear_tf=True)
    model = LogisticRegression(max_iter=1000, class_weight="balanced", solver="liblinear", random_state=42)
    predictions = model.fit(vectorizer.fit_transform(x_train), y_train).predict(vectorizer.transform(x_test))
    fp = sum(actual == 0 and predicted == 1 for actual, predicted in zip(y_test, predictions))
    tn = sum(actual == 0 and predicted == 0 for actual, predicted in zip(y_test, predictions))
    measured = {
        "csv_records": len(texts), "eval_set_v1_records": read_eval_count(),
        "train_rows": len(x_train), "test_rows": len(x_test),
        "accuracy": accuracy_score(y_test, predictions),
        "precision": precision_score(y_test, predictions, zero_division=0),
        "recall": recall_score(y_test, predictions, zero_division=0),
        "f1_score": f1_score(y_test, predictions, zero_division=0),
        "fp": int(fp), "tn": int(tn), "false_positive_rate": float(fp / (fp + tn)) if fp + tn else None,
    }
    print("metadata_metrics=" + json.dumps(metadata.get("metrics", {}), sort_keys=True))
    print("measured=" + json.dumps(measured, sort_keys=True))


if __name__ == "__main__":
    main()
