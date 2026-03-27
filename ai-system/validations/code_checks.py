"""
Code-level verify gates.

Required gates for 'code' and 'hybrid' tasks:
  - file_applied: patches/writes actually applied
  - file_not_empty: modified files are non-empty
  - py_syntax: Python files have valid syntax
  - no_rollback: rollback was NOT the final outcome
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from agents.shared.models import ValidationCheck


def gate_file_applied(task_context: dict[str, Any]) -> ValidationCheck:
    """Required: at least one file change was successfully applied."""
    patches = task_context.get("patches_applied", [])
    files = task_context.get("files_applied", [])

    applied_patches = [p for p in patches if p.get("status") == "applied"]
    written_files = [f for f in files if f.get("status") == "written"]
    total = len(applied_patches) + len(written_files)

    if not patches and not files:
        return ValidationCheck(
            check_name="gate:file_applied",
            check_type="code",
            passed=True,
            message="N/A (no file changes requested)",
        )

    return ValidationCheck(
        check_name="gate:file_applied",
        check_type="code",
        passed=total > 0,
        message=f"{total} file change(s) applied" if total else "No file changes applied",
    )


def gate_file_not_empty(
    task_context: dict[str, Any], repo_root: str
) -> ValidationCheck:
    """Required: modified files are non-empty on disk."""
    patches = task_context.get("patches_applied", [])
    files = task_context.get("files_applied", [])

    applied_paths = [
        p["path"] for p in patches if p.get("status") == "applied"
    ] + [
        f["path"] for f in files if f.get("status") == "written"
    ]

    if not applied_paths:
        return ValidationCheck(
            check_name="gate:file_not_empty",
            check_type="code",
            passed=True,
            message="N/A (no applied files)",
        )

    root = Path(repo_root).resolve()
    empty = []
    for rel in applied_paths:
        full = (root / rel).resolve()
        if full.exists() and full.stat().st_size == 0:
            empty.append(rel)

    return ValidationCheck(
        check_name="gate:file_not_empty",
        check_type="code",
        passed=len(empty) == 0,
        message=(
            f"All {len(applied_paths)} file(s) non-empty"
            if not empty
            else f"Empty files: {empty}"
        ),
    )


def gate_py_syntax(
    task_context: dict[str, Any], repo_root: str
) -> ValidationCheck:
    """Required: Python files have valid syntax after modification."""
    patches = task_context.get("patches_applied", [])
    files = task_context.get("files_applied", [])

    py_paths = [
        p["path"] for p in patches
        if p.get("status") == "applied" and p["path"].endswith(".py")
    ] + [
        f["path"] for f in files
        if f.get("status") == "written" and f["path"].endswith(".py")
    ]

    if not py_paths:
        return ValidationCheck(
            check_name="gate:py_syntax",
            check_type="code",
            passed=True,
            message="N/A (no Python files modified)",
        )

    root = Path(repo_root).resolve()
    errors = []
    for rel in py_paths:
        full = (root / rel).resolve()
        if not full.exists():
            continue
        try:
            ast.parse(full.read_text(encoding="utf-8"), filename=rel)
        except SyntaxError as e:
            errors.append(f"{rel}:{e.lineno}: {e.msg}")

    return ValidationCheck(
        check_name="gate:py_syntax",
        check_type="code",
        passed=len(errors) == 0,
        message=(
            f"All {len(py_paths)} Python file(s) have valid syntax"
            if not errors
            else f"Syntax errors: {errors}"
        ),
    )


def gate_no_rollback(task_context: dict[str, Any]) -> ValidationCheck:
    """Required: rollback was NOT the final outcome."""
    rolled_back = task_context.get("rollback_executed", False)
    return ValidationCheck(
        check_name="gate:no_rollback",
        check_type="code",
        passed=not rolled_back,
        message="No rollback" if not rolled_back else "Rollback was executed — task cannot be done",
    )
