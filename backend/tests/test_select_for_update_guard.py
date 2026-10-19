"""Guard: every ``select_for_update()`` in first-party code runs in a transaction.

``select_for_update()`` raises ``TransactionManagementError`` unless the query
runs inside an atomic block. Because Django's ``TestCase`` wraps every test in
one, a service that forgets its own transaction still passes the whole suite
and then 500s in production — which is how a balance-locking service once
shipped broken.

The rule enforced here has two halves:

1. Lexically inside ``transaction.atomic()`` — either a ``with`` block or a
   ``@transaction.atomic`` decorator. This is the normal case.
2. Otherwise the enclosing function's docstring must declare
   ``must be called inside transaction.atomic()``, meaning the transaction is
   deliberately supplied by the caller. That phrasing matches the convention
   already used by ``leave.services.references``.

   Both halves are required. ``leave.services.submission.record_revision``
   says "must be called inside the same transaction that writes the snapshot"
   for ordinary atomicity and has no lock, so it is neither an exception nor a
   stale one.

A marker that no longer guards any ``select_for_update()`` is reported too, so
exceptions cannot quietly outlive the code they described.
"""

import ast
import pathlib

from django.test import SimpleTestCase

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {".venv", "migrations", "__pycache__", "node_modules", "tests"}
MARKER = "must be called inside"


def _is_atomic_expr(node: ast.AST) -> bool:
    """``transaction.atomic`` / ``atomic``, with or without a call."""
    if isinstance(node, ast.Attribute):
        return node.attr == "atomic"
    if isinstance(node, ast.Name):
        return node.id == "atomic"
    return False


def _is_atomic_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _is_atomic_expr(node.func)


def _is_select_for_update(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "select_for_update"
    )


def _declares_marker(function: ast.AST) -> bool:
    docstring = (ast.get_docstring(function) or "").lower()
    return MARKER in docstring and "transaction.atomic" in docstring


def _has_atomic_decorator(function) -> bool:
    for decorator in function.decorator_list:
        if _is_atomic_expr(decorator) or _is_atomic_call(decorator):
            return True
    return False


def _iter_source_files():
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name == "tests.py" or path.name.startswith("test_"):
            continue
        yield path


def _scan():
    """Return ``(violations, stale_markers)`` for every first-party module."""
    violations = []
    stale = []

    for path in _iter_source_files():
        relative = path.relative_to(ROOT)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        def walk(node, *, in_atomic, function):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = node
                if _has_atomic_decorator(node):
                    in_atomic = True
                if _declares_marker(node) and not _contains_select_for_update(node):
                    stale.append(f"{relative}:{node.lineno} {node.name}")
            if isinstance(node, (ast.With, ast.AsyncWith)):
                if any(
                    _is_atomic_expr(item.context_expr)
                    or _is_atomic_call(item.context_expr)
                    for item in node.items
                ):
                    in_atomic = True
            if _is_select_for_update(node) and not in_atomic:
                if function is None or not _declares_marker(function):
                    owner = function.name if function is not None else "<module>"
                    violations.append(f"{relative}:{node.lineno} {owner}")
            for child in ast.iter_child_nodes(node):
                walk(child, in_atomic=in_atomic, function=function)

        walk(tree, in_atomic=False, function=None)

    return violations, stale


def _contains_select_for_update(function) -> bool:
    return any(_is_select_for_update(node) for node in ast.walk(function))


class SelectForUpdateGuardTests(SimpleTestCase):
    def test_every_select_for_update_runs_in_a_transaction(self):
        violations, _stale = _scan()
        self.assertEqual(
            violations,
            [],
            "select_for_update() outside a transaction. Wrap the function in "
            "transaction.atomic(), or document 'must be called inside "
            "transaction.atomic()' on the caller-supplied helper:\n  "
            + "\n  ".join(violations),
        )

    def test_no_stale_transaction_markers(self):
        _violations, stale = _scan()
        self.assertEqual(
            stale,
            [],
            "These functions declare 'must be called inside "
            "transaction.atomic()' but contain no select_for_update(), so the "
            "exception no longer applies:\n  " + "\n  ".join(stale),
        )
