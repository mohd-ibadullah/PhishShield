from __future__ import annotations

import json
import re
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR.parent / "data" / "Phishing_Email.csv"
MODEL_PATH = BASE_DIR / "model.pkl"
VECTORIZER_PATH = BASE_DIR / "vectorizer.pkl"
METADATA_PATH = BASE_DIR.parent / "data" / "training_meta.json"
OOD_EVAL_PATH = BASE_DIR.parent / "diagnostics" / "eval_set_v1.jsonl"
REPO_RELATIVE_DATASET_PATH = "data/Phishing_Email.csv"

LABEL_MAP = {
    "Phishing Email": 1,
    "Safe Email": 0,
    "phishing": 1,
    "safe": 0,
}


def clean_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_training_metadata(
    *,
    rows: int,
    train_rows: int,
    test_rows: int,
    metrics: dict[str, float],
    ood_holdout: dict[str, object],
) -> dict[str, object]:
    """Return the deterministic canonical metadata for this trainer recipe."""
    return {
        "dataset_path": REPO_RELATIVE_DATASET_PATH,
        "rows": rows,
        "train_rows": train_rows,
        "test_rows": test_rows,
        "metrics": metrics,
        "ood_holdout": ood_holdout,
    }


def measure_ood_holdout(
    vectorizer: TfidfVectorizer, model: LogisticRegression
) -> dict[str, object]:
    """Honest generalization measurement: score the committed adversarial
    holdout (diagnostics/eval_set_v1.jsonl) — hand-authored real-world rows
    that never appear in the training CSV. In-distribution scores near 1.0
    do not measure generalization; this bucket does."""
    if not OOD_EVAL_PATH.exists():
        return {"source": "diagnostics/eval_set_v1.jsonl", "available": False}

    items: list[dict[str, str]] = []
    with OOD_EVAL_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict) or not obj.get("text") or obj.get("label") not in LABEL_MAP:
                raise ValueError(f"Invalid OOD holdout row: {str(obj)[:80]!r}")
            items.append(obj)

    texts = [clean_text(str(i["text"])) for i in items]
    labels = [LABEL_MAP[i["label"]] for i in items]
    predictions = model.predict(vectorizer.transform(texts))

    fp = sum(a == 0 and p == 1 for a, p in zip(labels, predictions))
    tn = sum(a == 0 and p == 0 for a, p in zip(labels, predictions))
    return {
        "source": "diagnostics/eval_set_v1.jsonl",
        "rows": len(labels),
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1_score": float(f1_score(labels, predictions, zero_division=0)),
        "fp": int(fp),
        "tn": int(tn),
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else None,
        "note": (
            "Hand-authored adversarial/real-world holdout; none of these rows "
            "appear in the training CSV. This is the honest generalization "
            "measurement — the easy in-distribution training split is not."
        ),
    }


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH)
    columns = {str(col).strip() for col in df.columns}

    if {"Email Text", "Email Type"}.issubset(columns):
        df = df[["Email Text", "Email Type"]].dropna().copy()
        df["label"] = df["Email Type"].astype(str).map(LABEL_MAP)
        text_column = "Email Text"
    elif {"email_text", "label"}.issubset(columns):
        df = df[["email_text", "label"]].dropna().copy()
        df["label"] = df["label"].astype(str).str.strip().str.lower().map(LABEL_MAP)
        text_column = "email_text"
    else:
        raise ValueError(
            "Dataset must include either ['Email Text', 'Email Type'] or ['email_text', 'label'] columns."
        )

    if df["label"].isna().any():
        label_col = "Email Type" if text_column == "Email Text" else "label"
        unknown_labels = sorted(df.loc[df["label"].isna(), label_col].astype(str).unique().tolist())
        raise ValueError(f"Unsupported label values found: {unknown_labels}")

    df["clean_text"] = df[text_column].astype(str).apply(clean_text)

    X_train, X_test, y_train, y_test = train_test_split(
        df["clean_text"],
        df["label"],
        test_size=0.2,
        random_state=42,
        stratify=df["label"],
    )

    vectorizer = TfidfVectorizer(
        max_features=30000,
        ngram_range=(1, 2),
        min_df=2,
        stop_words="english",
        sublinear_tf=True,
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        solver="liblinear",
        random_state=42,
    )
    model.fit(X_train_vec, y_train)

    y_pred = model.predict(X_test_vec)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
    }

    print("=== PhishShield Model Training Complete ===")
    print(f"Dataset rows: {len(df):,}")
    print(f"Training rows: {len(X_train):,}")
    print(f"Testing rows: {len(X_test):,}")
    print(f"Accuracy : {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall   : {metrics['recall']:.4f}")
    print(f"F1 Score : {metrics['f1_score']:.4f}")

    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)

    ood_holdout = measure_ood_holdout(vectorizer, model)
    print("=== OOD holdout (diagnostics/eval_set_v1.jsonl) ===")
    if ood_holdout.get("available") is False:
        print("OOD eval set absent — ood_holdout marked unavailable")
    else:
        print(f"Rows     : {ood_holdout['rows']}")
        print(f"Accuracy : {ood_holdout['accuracy']:.4f}")
        print(f"Precision: {ood_holdout['precision']:.4f}")
        print(f"Recall   : {ood_holdout['recall']:.4f}")
        print(f"F1 Score : {ood_holdout['f1_score']:.4f}")
        print(f"FPR      : {ood_holdout['false_positive_rate']}")

    metadata = build_training_metadata(
        rows=int(len(df)),
        train_rows=int(len(X_train)),
        test_rows=int(len(X_test)),
        metrics=metrics,
        ood_holdout=ood_holdout,
    )
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved model to      : {MODEL_PATH}")
    print(f"Saved vectorizer to : {VECTORIZER_PATH}")
    print(f"Saved metadata to   : {METADATA_PATH}")


if __name__ == "__main__":
    main()
