"""Verify that every .py file under tests/ can be compiled.

This prevents the class of defect where a file sits in collect_ignore
because it has a syntax error, and nobody notices.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# Files that are excluded from collection by collect_ignore in conftest.py
# and are known not to be importable by pytest (manual scripts, live-server
# integration, etc.).  They are still checked for syntax validity.
_COLLECT_IGNORED = {
    "test_advanced_detection.py",
    "test_harness.py",
    "test_e2e.py",
    "test_script.py",
    "test_scan_simple.py",
    "test_wsbroadcast.py",
    "test_10_cases.py",
    "test_phishshield_cases.py",
}


def test_all_test_files_are_syntactically_valid() -> None:
    """Every .py file in tests/ must parse without SyntaxError."""
    errors: list[str] = []
    for py_file in sorted(TESTS_DIR.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{py_file.name}: {exc}")
    assert not errors, (
        "The following test files have syntax errors and cannot be imported:\n"
        + "\n".join(errors)
    )
