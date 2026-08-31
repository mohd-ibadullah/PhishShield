"""Verify tools/ manifest is up to date.

Every tools/*.py file that contains a def test_ function must be listed
in tools/README.md. This prevents test functions from becoming invisible.
"""
import glob
import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
README = TOOLS_DIR / "README.md"


def _files_with_test_functions():
    """Return list of tools/*.py files that contain def test_ functions."""
    result = []
    for py in sorted(TOOLS_DIR.glob("test_*.py")):
        content = py.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^def test_", content, re.MULTILINE):
            result.append(py.name)
    return result


def _files_listed_in_readme():
    """Return set of filenames mentioned in tools/README.md table."""
    if not README.exists():
        return set()
    content = README.read_text(encoding="utf-8")
    return set(re.findall(r"\|\s*(test_\w+\.py)\s*\|", content))


def test_tools_manifest_covers_test_functions():
    """Every tools/*.py with def test_ must be listed in README."""
    with_functions = _files_with_test_functions()
    listed = _files_listed_in_readme()
    missing = set(with_functions) - listed
    assert not missing, (
        f"tools/*.py files with def test_ but not in README.md: {missing}"
    )


def test_all_tools_py_are_compiled():
    """Every tools/*.py must be valid Python (py_compile catches syntax errors)."""
    import py_compile
    for py in sorted(TOOLS_DIR.glob("*.py")):
        py_compile.compile(str(py), doraise=True)


def test_all_tools_import_safely_as_module():
    """Every tools/*.py must import without blocking or sys.exit.

    Checks three failure modes:
    1. sys.exit on import (SystemExit in stderr)
    2. Traceback on import (non-zero exit + traceback in stderr)
    3. Timeout (script blocks on import, e.g. requests.get or input())
    """
    import subprocess
    import sys
    tools_dir = Path(__file__).resolve().parents[1] / "tools"
    sys_exit_failures = []
    import_failures = []
    timeout_failures = []
    for py in sorted(tools_dir.glob("*.py")):
        if py.name == "__init__.py":
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-c",
                 f"import importlib.util; s=importlib.util.spec_from_file_location('m','{py}'); " +
                 f"m=importlib.util.module_from_spec(s); s.loader.exec_module(m)"],
                capture_output=True, text=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            timeout_failures.append(py.name)
            continue
        stderr = result.stderr or ""
        if "SystemExit" in stderr:
            sys_exit_failures.append((py.name, stderr.strip()[:200]))
        elif result.returncode != 0 and "Traceback" in stderr:
            import_failures.append((py.name, stderr.strip()[:200]))
    errors = []
    if sys_exit_failures:
        errors.append(f"sys.exit on import: {sys_exit_failures}")
    if import_failures:
        errors.append(f"import traceback: {import_failures}")
    if timeout_failures:
        errors.append(f"blocks on import (timeout 10s): {timeout_failures}")
    assert not errors, "tools/*.py import failures: " + " | ".join(errors)
