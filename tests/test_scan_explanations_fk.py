"""B2: scan_explanations FK migration + orphan purge (V43).

Legacy DBs created without the FK must be rebuilt in place (create _new,
copy, drop, rename), orphaned explanation rows purged with the count logged,
and PRAGMA foreign_keys=ON applied on every connect so deletes cascade.
"""
from __future__ import annotations

import pathlib
import sqlite3
import sys

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as bm


@pytest.fixture()
def legacy_db(tmp_path, monkeypatch):
    """A scans DB in the pre-FK shape, seeded with owned + orphan rows."""
    db_path = tmp_path / "scans-legacy.db"
    monkeypatch.setattr(bm, "SCANS_DB_PATH", db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE scans (
            scan_id TEXT PRIMARY KEY,
            session_id TEXT,
            verdict TEXT,
            risk_score INTEGER,
            timestamp TEXT,
            language TEXT,
            sender_domain TEXT
        )
        """
    )
    # Legacy scan_explanations WITHOUT the FK clause.
    conn.execute(
        """
        CREATE TABLE scan_explanations (
            scan_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO scans (scan_id, session_id, verdict, risk_score, timestamp, language, sender_domain) "
        "VALUES ('owned-1', '', 'Safe', 10, '2026-01-01', 'EN', '')"
    )
    # FK off so legacy orphan rows can exist.
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO scan_explanations (scan_id, payload_json, updated_at) VALUES "
        "('owned-1', '{}', '2026-01-01'), "
        "('orphan-1', '{}', '2026-01-01'), "
        "('orphan-2', '{}', '2026-01-01')"
    )
    conn.commit()
    conn.close()
    return db_path


def test_orphans_removed_and_fk_added_on_startup(legacy_db):
    """Boot the same path startup uses (ensure_scans_db) and assert V43's invariants."""
    bm.ensure_scans_db()

    conn = sqlite3.connect(legacy_db)
    orphans = conn.execute(
        "SELECT COUNT(*) FROM scan_explanations WHERE scan_id NOT IN (SELECT scan_id FROM scans)"
    ).fetchone()[0]
    fk = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%ON DELETE CASCADE%'"
    ).fetchone()[0]
    scans, expl = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0], conn.execute(
        "SELECT COUNT(*) FROM scan_explanations"
    ).fetchone()[0]
    conn.close()

    assert orphans == 0, f"orphans remain: {orphans}"
    assert fk >= 1, "ON DELETE CASCADE missing from sqlite_master"
    assert expl == 1, f"owned explanation should survive, got {expl}"
    assert scans == 1


def test_delete_cascades_to_explanations(legacy_db):
    """With foreign_keys=ON on every connect, deleting a scan removes its explanations."""
    bm.ensure_scans_db()

    conn = bm._connect_scans_db()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("DELETE FROM scans WHERE scan_id = 'owned-1'")
    conn.commit()
    remaining = conn.execute("SELECT COUNT(*) FROM scan_explanations").fetchone()[0]
    conn.close()
    assert remaining == 0, f"cascade did not remove explanations: {remaining}"