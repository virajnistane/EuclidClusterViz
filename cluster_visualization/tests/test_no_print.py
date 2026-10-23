"""App modules log through loguru; print() only where its output is the product.

New print() calls outside the allowlist fail this test. PENDING lists the modules not
converted yet; remove a module from it once its prints are log calls.
"""

import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]

# Whole files: CLI scripts whose stdout is their output, and dev tools
ALLOWED_FILES = {
    "scripts/generate_mask_hips.py",
    "scripts/generate_catalog_catred_matches.py",
    "scripts/write_prefetch_manifest.py",
    "src/test_dash_app.py",
    "utils/fix_syntax.py",
}

# Single functions that print for the user, not log
ALLOWED_FUNCTIONS = {
    # Runs before the dependency check: loguru itself may be missing
    "src/cluster_dash_app.py": {"check_environment"},
    # Startup banner, SSH tunnel box and the "no users connected" box
    "core/app.py": {"run", "check_connections"},
}

# Not converted yet (removed module by module)
PENDING: set = set()


def print_calls(tree):
    """(line, enclosing function name or None) for each print() call."""
    found = []

    def visit(node, func):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = node.name
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            found.append((node.lineno, func))
        for child in ast.iter_child_nodes(node):
            visit(child, func)

    visit(tree, None)
    return found


def module_files():
    for path in sorted(PACKAGE.rglob("*.py")):
        rel = path.relative_to(PACKAGE).as_posix()
        if rel.startswith(("tests/", "docs/")) or "__pycache__" in rel:
            continue
        yield rel, path


def _calls(path):
    return print_calls(ast.parse(path.read_text(encoding="utf-8")))


class TestNoPrint(unittest.TestCase):
    def test_no_print_outside_allowlist(self):
        offenders = []
        for rel, path in module_files():
            if rel in ALLOWED_FILES or rel in PENDING:
                continue
            allowed = ALLOWED_FUNCTIONS.get(rel, set())
            offenders += [f"{rel}:{line}" for line, func in _calls(path) if func not in allowed]
        self.assertEqual(offenders, [], "use loguru's logger instead of print()")

    def test_pending_list_is_current(self):
        """A converted module must leave PENDING, so the guard covers it."""
        files = dict(module_files())
        stale = [rel for rel in sorted(PENDING) if rel not in files or not _calls(files[rel])]
        self.assertEqual(stale, [], "remove these from PENDING")


if __name__ == "__main__":
    unittest.main()
