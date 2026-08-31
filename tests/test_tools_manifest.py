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
