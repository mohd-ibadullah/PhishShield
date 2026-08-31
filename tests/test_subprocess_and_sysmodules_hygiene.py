"""Structural hygiene meta-tests — make two leak classes impossible to reintroduce.

Class 1 — sys.modules mutation without restore: any test module that mutates
sys.modules (subscript assign/delete of ``sys.modules[...]`` or
``importlib.reload``) MUST reference the conftest restore helpers
(``sys_modules_guard`` fixture or ``register_sys_modules_restore()``).
This is the class that caused the ordering-dependent store leak: an
evicted-and-reimported ``main`` escaped the conftest store redirect.

Class 2 — uncontained subprocess pytest: any test module that actually
CALLS ``subprocess.run/Popen/check_output/check_call/call`` (or
``os.system/os.popen``) to run pytest MUST:
  - reference ``PHISHSHIELD_STORE_DIR`` (the one store-redirect knob both
    parent and child resolve store paths from), and
  - pass at least one explicit ``tests/test_*.py`` target constant (a
    bounded subset), and
  - never pass the whole ``tests`` directory as the target.

A runtime identity net additionally asserts that ``sys.modules['main']`` is
still the object conftest imported — so an unregistered eviction that slips
past the static scan fails here at collection-order time (this file sorts
after every module that legitimately mutates sys.modules).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from conftest import _ORIGINAL_MAIN

TESTS_DIR = Path(__file__).resolve().parent

RESTORE_MARKERS = ("sys_modules_guard", "register_sys_modules_restore")
STORE_REDIRECT_KNOB = "PHISHSHIELD_STORE_DIR"
_WHOLE_SUITE_TARGETS = {"tests", "tests/", "tests\\"}

_SUBPROCESS_CALLS = {"run", "Popen", "check_output", "check_call", "call"}
_OS_SPAWN_CALLS = {"system", "popen"}


def _iter_test_files():
    for py in sorted(TESTS_DIR.glob("*.py")):
        if py.name.startswith("__") or py.name == "conftest.py":
            continue
        yield py


def _is_sys_modules_subscript(node: ast.AST) -> bool:
    """True for `<anything>.modules[...]` where the base is the sys module."""
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "modules"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
    )


def _sys_modules_mutations(tree: ast.Module) -> list[str]:
    """Descriptions of sys.modules mutations (assign/delete) + importlib.reload."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            for t in targets:
                if _is_sys_modules_subscript(t):
                    found.append(f"line {node.lineno}: sys.modules subscript mutation")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "reload" and isinstance(node.func.value, ast.Name) and node.func.value.id in ("importlib", "reload"):
                found.append(f"line {node.lineno}: importlib.reload")
    return found


def _subprocess_pytest_calls(tree: ast.Module) -> list[ast.Call]:
    """subprocess/os calls that could spawn pytest."""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        base = node.func.value
        if not isinstance(base, ast.Name):
            continue
        if (base.id == "subprocess" and node.func.attr in _SUBPROCESS_CALLS) or (
            base.id == "os" and node.func.attr in _OS_SPAWN_CALLS
        ):
            calls.append(node)
    return calls


def _module_level_const_lists(tree: ast.Module) -> dict[str, list[str]]:
    """Map module-level `NAME = ["a", "b"]` string-list constants."""
    out: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and isinstance(node.value, (ast.List, ast.Tuple)):
                    vals = [e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                    if vals:
                        out[t.id] = vals
    return out


def _const_strs(node: ast.AST, lists: dict[str, list[str]] | None = None) -> list[str]:
    out: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Starred) and isinstance(sub.value, ast.Name) and lists:
            out.extend(lists.get(sub.value.id, []))
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
    return out


def _is_pytest_invocation(call: ast.Call) -> bool:
    return any(s == "pytest" for s in _const_strs(call))


# ── Class 1: sys.modules mutation must be registered for restore ─────

def test_sys_modules_mutations_are_registered_for_restore():
    offenders: list[str] = []
    for py in _iter_test_files():
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        mutations = _sys_modules_mutations(tree)
        if not mutations:
            continue
        src = py.read_text(encoding="utf-8")
        if not any(m in src for m in RESTORE_MARKERS):
            offenders.append(f"{py.name}: {len(mutations)} mutation(s), no registered restore")
    assert not offenders, (
        "Tests mutate sys.modules without a registered restore "
        f"(use the conftest sys_modules_guard fixture or register_sys_modules_restore): "
        + "; ".join(offenders)
    )


# ── Class 2: subprocess pytest must be bounded + store-redirected ────

def test_subprocess_pytest_invocations_are_bounded_and_redirect_stores():
    offenders: list[str] = []
    for py in _iter_test_files():
        src_text = py.read_text(encoding="utf-8")
        tree = ast.parse(src_text, filename=str(py))
        lists = _module_level_const_lists(tree)
        calls = [c for c in _subprocess_pytest_calls(tree) if _is_pytest_invocation(c)]
        if not calls:
            continue
        if STORE_REDIRECT_KNOB not in src_text:
            offenders.append(f"{py.name}: spawns pytest but never references {STORE_REDIRECT_KNOB}")
            continue
        for call in calls:
            consts = _const_strs(call, lists)
            targets = [s for s in consts if s.startswith("tests") or s == "tests"]
            if any(t in _WHOLE_SUITE_TARGETS for t in targets):
                offenders.append(f"{py.name}: line {call.lineno}: spawns pytest on the whole tests/ dir")
            if not any(s.startswith(f"tests{chr(47)}") for s in consts):
                offenders.append(
                    f"{py.name}: line {call.lineno}: no explicit tests/test_*.py target — subset not provably bounded"
                )
    assert not offenders, "Unbounded or unredirected subprocess pytest invocations: " + "; ".join(offenders)


# ── Runtime identity net ─────────────────────────────────────────────

def test_main_module_is_unchanged_by_earlier_tests():
    """sys.modules['main'] must still be the object conftest imported.

    This file is collected after every module that legitimately mutates
    sys.modules (alphabetical order, -p no:randomly); if an eviction without
    restore ran earlier in the session, this catches it at runtime.
    """
    current = sys.modules.get("main")
    assert current is _ORIGINAL_MAIN, (
        "sys.modules['main'] was replaced during the session and not restored: "
        f"got {current!r}, expected the conftest-imported {_ORIGINAL_MAIN!r}"
    )
