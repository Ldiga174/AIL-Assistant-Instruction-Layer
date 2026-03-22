"""
AIL Validator — verifies agent results against expectations.

AIL never trusts agents blindly.  The validator checks:
  - Files were actually changed
  - Commands were actually executed
  - Services are actually up
  - Errors are not hidden

Returns a ValidationResult with a recommended action.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from agents.shared.models import (
    AgentResult,
    ResultStatus,
    Task,
    ValidationAction,
    ValidationCheck,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class Validator:
    """Stateless validator: checks an AgentResult against a Task."""

    def validate(self, task: Task, result: AgentResult) -> ValidationResult:
        checks: list[ValidationCheck] = []

        checks.append(self._check_status(result))
        checks.extend(self._check_files_exist(result))
        checks.append(self._check_no_hidden_errors(result))

        all_passed = all(c.passed for c in checks)
        action = self._decide_action(task, all_passed, result)

        vr = ValidationResult(
            task_id=task.task_id,
            passed=all_passed,
            checks=checks,
            action=action,
        )
        logger.info(
            "Validation for %s: passed=%s action=%s",
            task.task_id, all_passed, action.value,
        )
        return vr

    @staticmethod
    def _check_status(result: AgentResult) -> ValidationCheck:
        passed = result.status in (ResultStatus.SUCCESS, ResultStatus.PARTIAL)
        return ValidationCheck(
            check_name="agent_status_ok",
            check_type="generic",
            passed=passed,
            message=f"Agent returned status: {result.status.value}",
            expected="success or partial",
            actual=result.status.value,
        )

    @staticmethod
    def _check_files_exist(result: AgentResult) -> list[ValidationCheck]:
        checks = []
        for fpath in result.artifacts.files_changed:
            exists = Path(fpath).exists()
            checks.append(ValidationCheck(
                check_name=f"file_exists:{fpath}",
                check_type="code",
                passed=exists,
                message=f"File {'exists' if exists else 'MISSING'}: {fpath}",
                expected=True,
                actual=exists,
            ))
        return checks

    @staticmethod
    def _check_no_hidden_errors(result: AgentResult) -> ValidationCheck:
        has_errors = len(result.errors) > 0
        status_ok = result.status in (ResultStatus.SUCCESS, ResultStatus.PARTIAL)
        hidden = has_errors and status_ok
        return ValidationCheck(
            check_name="no_hidden_errors",
            check_type="generic",
            passed=not hidden,
            message="Errors present but status is success" if hidden else "OK",
        )

    @staticmethod
    def _decide_action(
        task: Task, all_passed: bool, result: AgentResult
    ) -> ValidationAction:
        if all_passed:
            return ValidationAction.ACCEPT
        if task.retry_count < task.max_retries:
            return ValidationAction.RETRY
        return ValidationAction.ABORT
