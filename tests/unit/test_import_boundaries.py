"""heal.core must stay free of Robot Framework and automation-library imports.

The core engine is pure: it operates on typed schemas and protocols so it can
run in CLI/MCP contexts and be unit-tested without RF or a browser. This test
walks the AST of every module under heal/core and fails on forbidden imports.
"""

import ast
from pathlib import Path

import heal.core

FORBIDDEN_ROOTS = {"robot", "Browser", "AppiumLibrary", "selenium", "appium"}

CORE_DIR = Path(heal.core.__file__).parent


def iter_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                yield node.module


def test_core_does_not_import_rf_or_drivers():
    violations = []
    for py_file in CORE_DIR.rglob("*.py"):
        for module in iter_imports(py_file):
            root = module.split(".")[0]
            if root in FORBIDDEN_ROOTS:
                violations.append(f"{py_file.relative_to(CORE_DIR.parent.parent)}: imports {module}")
    assert not violations, "heal.core must not depend on RF/automation libs:\n" + "\n".join(violations)
