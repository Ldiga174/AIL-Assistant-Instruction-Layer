"""
AIL Validator — verifies agent results.

AIL never trusts agents blindly. Four mandatory checks:

  1. Agent returned a non-empty result (task_id + agent present)
  2. Status is not empty
  3. If status == success  ->  at least one artifact OR a non-empty note
  4. If status == error/failed  ->  at least one error with text description

Returns a ValidationResult with a recommended action (accept / retry / abort).
"""

from __future__ import annotations

import logging

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
    """Stateless validator: checks an AgentResult against the 4 rules."""

    def validate(self, task: Task, result: AgentResult) -> ValidationResult:
        checks: list[ValidationCheck] = [
            self._check_result_not_empty(result),
            self._check_status_present(result),
            self._check_success_has_content(result),
            self._check_error_has_description(result),
        ]

        all_passed = all(c.passed for c in checks)
        action = self._decide_action(task, all_passed)

        vr = ValidationResult(
            task_id=task.task_id,
            passed=all_passed,
            checks=checks,
            action=action,
        )

        logger.info(
            "Validation %s [%s]: passed=%s action=%s (%d checks)",
            task.task_id,
            result.agent.value,
            all_passed,
            action.value,
            len(checks),
        )
        return vr

    @staticmethod
    def _check_result_not_empty(result: AgentResult) -> ValidationCheck:
        """Check 1: agent returned a non-empty result."""
        has_id = bool(result.task_id)
        has_agent = bool(result.agent)
        passed = has_id and has_agent
        return ValidationCheck(
            check_name="result_not_empty",
            check_type="generic",
            passed=passed,
            message="Result contains task_id and agent" if passed else "Result is missing task_id or agent",
        )

    @staticmethod
    def _check_status_present(result: AgentResult) -> ValidationCheck:
        """Check 2: status is not empty."""
        passed = bool(result.status and result.status.value)
        return ValidationCheck(
            check_name="status_present",
            check_type="generic",
            passed=passed,
            message=f"Status: {result.status.value}" if passed else "Status is empty",
        )

    @staticmethod
    def _check_success_has_content(result: AgentResult) -> ValidationCheck:
        """Check 3: if success, at least one artifact or note must be present."""
        if result.status not in (ResultStatus.SUCCESS, ResultStatus.PARTIAL):
            return ValidationCheck(
                check_name="success_has_content",
                check_type="generic",
                passed=True,
                message="N/A (status is not success)",
            )

        has_artifacts = bool(
            result.artifacts.files_changed
            or result.artifacts.commands
            or result.artifacts.outputs
        )
        has_notes = bool(result.notes and result.notes.strip())
        passed = has_artifacts or has_notes

        parts = []
        if result.artifacts.files_changed:
            parts.append(f"{len(result.artifacts.files_changed)} files")
        if result.artifacts.commands:
            parts.append(f"{len(result.artifacts.commands)} commands")
        if has_notes:
            parts.append("notes present")

        return ValidationCheck(
            check_name="success_has_content",
            check_type="generic",
            passed=passed,
            message=", ".join(parts) if parts else "No artifacts and no notes — empty result",
        )

    @staticmethod
    def _check_error_has_description(result: AgentResult) -> ValidationCheck:
        """Check 4: if error/failed, at least one error with text description."""
        if result.status not in (ResultStatus.FAILED, ResultStatus.ERROR):
            return ValidationCheck(
                check_name="error_has_description",
                check_type="generic",
                passed=True,
                message="N/A (status is not error/failed)",
            )

        has_described_error = any(
            e.message and e.message.strip() for e in result.errors
        )
        return ValidationCheck(
            check_name="error_has_description",
            check_type="generic",
            passed=has_described_error,
            message=(
                f"{len(result.errors)} error(s) with description"
                if has_described_error
                else "Failed status but no error description provided"
            ),
        )

    @staticmethod
    def _decide_action(task: Task, all_passed: bool) -> ValidationAction:
        if all_passed:
            return ValidationAction.ACCEPT
        if task.retry_count < task.max_retries:
            return ValidationAction.RETRY
        return ValidationAction.ABORT
