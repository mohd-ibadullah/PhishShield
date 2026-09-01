"""Single source of truth for store file paths.

All guards, fixtures, and manifest tests import STORE_FILES from here.
DO NOT duplicate this list elsewhere.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STORE_FILES = [
    PROJECT_ROOT / "backend" / "scan_logs.jsonl",
    PROJECT_ROOT / "backend" / "scans.db",
    PROJECT_ROOT / "backend" / "feedback.csv",
    PROJECT_ROOT / "backend" / "sender_profiles.json",
    PROJECT_ROOT / "data" / "feedback.csv",
    PROJECT_ROOT / "data" / "feedback_memory.json",
    PROJECT_ROOT / "data" / "feedback_state.json",
]

STORE_LABELS = [
    ("scan_logs.jsonl", STORE_FILES[0]),
    ("scans.db", STORE_FILES[1]),
    ("feedback.csv", STORE_FILES[2]),
    ("sender_profiles.json", STORE_FILES[3]),
    ("data/feedback.csv", STORE_FILES[4]),
    ("feedback_memory.json", STORE_FILES[5]),
    ("feedback_state.json", STORE_FILES[6]),
]
