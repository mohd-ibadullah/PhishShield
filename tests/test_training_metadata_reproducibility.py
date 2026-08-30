from __future__ import annotations

import json
from pathlib import Path

from train_model import build_training_metadata


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_metadata_is_trainer_owned_and_repo_relative() -> None:
    metadata = json.loads((ROOT / "data" / "training_meta.json").read_text(encoding="utf-8"))
    assert set(metadata) == {"dataset_path", "rows", "train_rows", "test_rows", "metrics"}
    assert metadata["dataset_path"] == "data/Phishing_Email.csv"
    assert metadata == build_training_metadata(
        rows=2000,
        train_rows=1600,
        test_rows=400,
        metrics={"accuracy": 1.0, "precision": 1.0, "recall": 1.0, "f1_score": 1.0},
    )
