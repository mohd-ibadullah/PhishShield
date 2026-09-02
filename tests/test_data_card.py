"""T9: Dataset CARD exists and row count matches."""
from __future__ import annotations

import csv
import pathlib


def test_card_exists():
    card = pathlib.Path("data/CARD.md")
    assert card.exists(), "data/CARD.md does not exist"


def test_card_row_count_matches():
    csv_path = pathlib.Path("data/Phishing_Email.csv")
    card_path = pathlib.Path("data/CARD.md")
    if not csv_path.exists() or not card_path.exists():
        return
    actual_rows = sum(1 for _ in csv.reader(csv_path.open(encoding="utf-8", errors="replace"))) - 1
    card_text = card_path.read_text(encoding="utf-8")
    assert str(actual_rows) in card_text, f"Card row count does not match actual: {actual_rows}"
