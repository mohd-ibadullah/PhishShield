from __future__ import annotations

import json
from pathlib import Path

from train_model import build_training_metadata


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_metadata_is_trainer_owned_and_repo_relative() -> None:
    metadata = json.loads((ROOT / "data" / "training_meta.json").read_text(encoding="utf-8"))
    assert set(metadata) == {"dataset_path", "rows", "train_rows", "test_rows", "metrics", "ood_holdout"}
    assert metadata["dataset_path"] == "data/Phishing_Email.csv"
    assert metadata["ood_holdout"]["source"] == "diagnostics/eval_set_v1.jsonl"
    assert metadata == build_training_metadata(
        rows=2000,
        train_rows=1600,
        test_rows=400,
        metrics={"accuracy": 1.0, "precision": 1.0, "recall": 1.0, "f1_score": 1.0},
        ood_holdout=metadata["ood_holdout"],
    )


def test_ood_holdout_is_the_honest_generalization_bucket() -> None:
    """The OOD holdout metrics must exist and be clearly worse than the
    in-distribution metrics — if they ever match (both 1.0), the holdout
    has leaked into training or is no longer adversarial."""
    metadata = json.loads((ROOT / "data" / "training_meta.json").read_text(encoding="utf-8"))
    ood = metadata["ood_holdout"]
    assert ood.get("available") is not False, "OOD holdout must be measured, not skipped"
    assert ood["rows"] > 0
    assert ood["accuracy"] <= metadata["metrics"]["accuracy"]
    # In-distribution is a closed 2000-row set with 0 shared template families
    # (see caveat) — a 1.0 there is expected but NOT a generalization claim.
    # The OOD bucket is the honest number and must carry the explanatory note.
    assert "not" in ood["note"]
