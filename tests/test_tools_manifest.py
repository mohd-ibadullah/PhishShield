"""Verify tools/ manifest is up to date.

Every tools/*.py file that contains a def test_ function must be listed
in tools/README.md. This prevents test functions from becoming invisible.
"""
import glob
import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
README = TOOLS_DIR / "README.md"
_LISTING_RE = re.compile(r"\|\s*([\w.\-]+\.py)\s*\|")


def _files_with_test_functions():
    """Return list of tools/*.py files that contain def test_ functions."""
    result = []
    for py in sorted(TOOLS_DIR.glob("*.py")):
        content = py.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^def test_", content, re.MULTILINE):
            result.append(py.name)
    return result


def _files_listed_in_readme():
    """Return set of filenames mentioned in tools/README.md table."""
    if not README.exists():
        return set()
    content = README.read_text(encoding="utf-8")
    return set(_LISTING_RE.findall(content))


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


def test_guard_detects_unlisted_def_test_in_non_test_named_file(tmp_path, monkeypatch):
    """Planted violation: def test_ in a non-test_-named file must be caught."""
    import sys
    mod = sys.modules[__name__]
    fake_tools = tmp_path / "tools"
    fake_tools.mkdir()
    (fake_tools / "z_unlisted.py").write_bytes(b"def test_x(): pass\n")
    (fake_tools / "README.md").write_bytes(
        b"# Tools\n\n| File | Desc |\n|------|------|\n| other.py | desc |\n"
    )
    monkeypatch.setattr(mod, "TOOLS_DIR", fake_tools)
    monkeypatch.setattr(mod, "README", fake_tools / "README.md")
    with_functions = _files_with_test_functions()
    listed = _files_listed_in_readme()
    missing = set(with_functions) - listed
    assert missing, (
        f"Guard failed to detect unlisted def test_: with_functions={with_functions} "
        f"listed={listed}"
    )
    assert "z_unlisted.py" in missing


def test_guard_accepts_listed_file(tmp_path, monkeypatch):
    """Positive control: a non-test_-named file listed in README should pass."""
    import sys
    mod = sys.modules[__name__]
    fake_tools = tmp_path / "tools"
    fake_tools.mkdir()
    (fake_tools / "z_unlisted.py").write_bytes(b"def test_x(): pass\n")
    (fake_tools / "README.md").write_bytes(
        b"# Tools\n\n| File | Desc |\n|------|------|\n| z_unlisted.py | desc |\n"
    )
    monkeypatch.setattr(mod, "TOOLS_DIR", fake_tools)
    monkeypatch.setattr(mod, "README", fake_tools / "README.md")
    with_functions = _files_with_test_functions()
    listed = _files_listed_in_readme()
    missing = set(with_functions) - listed
    assert not missing, f"Guard falsely flagged listed file: {missing}"


def test_filename_mentioned_outside_table_is_not_listed(tmp_path, monkeypatch):
    """Negative control: a .py filename in prose or a code block must NOT
    count as 'listed'.  The listing regex is only as strict as its pipe
    anchors: prose containing a ``|`` (e.g. a shell pipe inside a table
    cell) would still count as listed.  If this test fails, the regex
    widened past pipe-delimited table rows.
    """
    import sys
    mod = sys.modules[__name__]
    fake_tools = tmp_path / "tools"
    fake_tools.mkdir()
    (fake_tools / "z_unlisted.py").write_bytes(b"def test_x(): pass\n")
    # README mentions z_unlisted.py ONLY in prose / code block, never in a table row
    (fake_tools / "README.md").write_bytes(
        b"# Tools\n\n"
        b"Run ``python tools/z_unlisted.py`` for details.\n\n"
        b"See also: tools/z_unlisted.py in the contributor guide.\n\n"
        b"| File | Desc |\n|------|------|\n| other.py | desc |\n"
    )
    monkeypatch.setattr(mod, "TOOLS_DIR", fake_tools)
    monkeypatch.setattr(mod, "README", fake_tools / "README.md")
    with_functions = _files_with_test_functions()
    listed = _files_listed_in_readme()
    missing = set(with_functions) - listed
    assert "z_unlisted.py" in missing, (
        f"Guard accepted z_unlisted.py from prose/code-block mention alone; "
        f"listed={listed}, missing={missing}"
    )


def test_listing_regex_is_table_only():
    """The listing regex is only as strict as its pipe anchors: prose
    containing a ``|`` (e.g. a shell pipe inside a table cell) would
    still count as listed."""
    assert _LISTING_RE.pattern == r"\|\s*([\w.\-]+\.py)\s*\|"
