"""
Code-level validation checks.

Used by AIL Validator to verify that OpenCode's output is legitimate:
  - Files actually exist on disk
  - Files were modified recently (not stale claims)
  - Python files have valid syntax
  - No obvious regressions (import errors, etc.)
"""

from __future__ import annotations

import ast
import os
import time
from pathlib import Path

from agents.shared.models import ValidationCheck


def check_files_exist(file_paths: list[str]) -> list[ValidationCheck]:
    """Verify that all claimed files actually exist."""
    checks = []
    for fp in file_paths:
        exists = Path(fp).exists()
        checks.append(ValidationCheck(
            check_name=f"file_exists:{fp}",
            check_type="code",
            passed=exists,
            message=f"{'Exists' if exists else 'MISSING'}: {fp}",
            expected=True,
            actual=exists,
        ))
    return checks


def check_files_modified_recently(
    file_paths: list[str], max_age_seconds: int = 300
) -> list[ValidationCheck]:
    """Verify files were modified within the expected time window."""
    checks = []
    now = time.time()
    for fp in file_paths:
        p = Path(fp)
        if not p.exists():
            checks.append(ValidationCheck(
                check_name=f"file_fresh:{fp}",
                check_type="code",
                passed=False,
                message=f"File does not exist: {fp}",
            ))
            continue
        age = now - p.stat().st_mtime
        fresh = age <= max_age_seconds
        checks.append(ValidationCheck(
            check_name=f"file_fresh:{fp}",
            check_type="code",
            passed=fresh,
            message=f"Age: {int(age)}s (limit: {max_age_seconds}s)",
            expected=f"<= {max_age_seconds}s",
            actual=f"{int(age)}s",
        ))
    return checks


def check_python_syntax(file_paths: list[str]) -> list[ValidationCheck]:
    """Verify that Python files have valid syntax."""
    checks = []
    for fp in file_paths:
        if not fp.endswith(".py"):
            continue
        p = Path(fp)
        if not p.exists():
            checks.append(ValidationCheck(
                check_name=f"py_syntax:{fp}",
                check_type="code",
                passed=False,
                message=f"File not found: {fp}",
            ))
            continue
        try:
            source = p.read_text(encoding="utf-8")
            ast.parse(source, filename=fp)
            checks.append(ValidationCheck(
                check_name=f"py_syntax:{fp}",
                check_type="code",
                passed=True,
                message="Valid Python syntax",
            ))
        except SyntaxError as e:
            checks.append(ValidationCheck(
                check_name=f"py_syntax:{fp}",
                check_type="code",
                passed=False,
                message=f"Syntax error at line {e.lineno}: {e.msg}",
            ))
    return checks
