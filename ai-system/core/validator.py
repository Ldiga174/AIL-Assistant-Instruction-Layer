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
    AgentName,
    AgentResult,
    ResultStatus,
    Task,
    TaskRole,
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
            self._check_capability_contract(result),
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
    def _check_capability_contract(result: AgentResult) -> ValidationCheck:
        """Check 5: agent did not produce forbidden output artifacts."""
        from core.capabilities import validate_agent_output
        violations = validate_agent_output(result)
        return ValidationCheck(
            check_name="capability_contract_ok",
            check_type="generic",
            passed=len(violations) == 0,
            message=(
                "No capability violations"
                if not violations
                else f"VIOLATIONS: {'; '.join(violations)}"
            ),
        )

    @staticmethod
    def _decide_action(task: Task, all_passed: bool) -> ValidationAction:
        if all_passed:
            return ValidationAction.ACCEPT
        if task.retry_count < task.max_retries:
            return ValidationAction.RETRY
        return ValidationAction.ABORT

    def validate_gates(
        self, task: Task, results: list[AgentResult]
    ) -> ValidationResult:
        """
        Run required verify gates based on task role.

        Gates are hard requirements — if any required gate fails,
        the task cannot be marked as done.

        Required gates by role:
          code:   file_applied, file_not_empty, py_syntax, no_rollback
          exec:   command_executed, no_total_failure
          hybrid: all code gates + all exec gates + verify_commands_ok
        """
        from pathlib import Path
        from validations.code_checks import (
            gate_file_applied,
            gate_file_not_empty,
            gate_no_rollback,
            gate_py_syntax,
        )
        from validations.deploy_checks import (
            gate_command_executed,
            gate_no_total_failure,
            gate_verify_commands_ok,
        )

        repo_root = str(Path(task.inputs.repo).resolve())
        ctx = task.inputs.context
        policy = ctx.get("_policy", {})

        required: list[ValidationCheck] = []
        optional: list[ValidationCheck] = []

        if policy.get("require_snapshot") and ctx.get("snapshot_created") is not None:
            snapshot_ok = bool(ctx.get("snapshot_created"))
            required.append(ValidationCheck(
                check_name="gate:snapshot_present",
                check_type="generic",
                passed=snapshot_ok,
                message="Snapshot was created" if snapshot_ok else "Snapshot MISSING (required by policy)",
            ))

        if task.role in (TaskRole.CODE, TaskRole.HYBRID):
            required.append(gate_file_applied(ctx))
            required.append(gate_file_not_empty(ctx, repo_root))
            required.append(gate_py_syntax(ctx, repo_root))
            required.append(gate_no_rollback(ctx))

        if task.role in (TaskRole.EXEC, TaskRole.HYBRID):
            required.append(gate_command_executed(results))
            required.append(gate_no_total_failure(results))

        if task.role == TaskRole.HYBRID:
            required.append(gate_verify_commands_ok(results))

        all_checks = required + optional
        required_passed = all(c.passed for c in required)
        all_passed = all(c.passed for c in all_checks)

        if required_passed:
            action = ValidationAction.ACCEPT
        else:
            action = ValidationAction.ABORT

        failed_gates = [c.check_name for c in required if not c.passed]

        logger.info(
            "Gates %s [%s]: required=%d passed=%s, failed=%s",
            task.task_id, task.role.value,
            len(required), required_passed,
            failed_gates or "none",
        )

        return ValidationResult(
            task_id=task.task_id,
            passed=all_passed,
            checks=all_checks,
            action=action,
        )

    def validate_snapshot(self, task: Task) -> ValidationResult:
        """Verify snapshot/rollback lifecycle for tasks with file changes."""
        checks: list[ValidationCheck] = []

        snapshot_created = task.inputs.context.get("snapshot_created")
        if snapshot_created is None:
            checks.append(ValidationCheck(
                check_name="snapshot",
                check_type="generic",
                passed=True,
                message="N/A (no file changes)",
            ))
            return ValidationResult(
                task_id=task.task_id, passed=True, checks=checks,
            )

        checks.append(ValidationCheck(
            check_name="snapshot_created",
            check_type="generic",
            passed=bool(snapshot_created),
            message="Snapshot created before apply" if snapshot_created else "Snapshot FAILED — changes should not have been applied",
        ))

        rollback_executed = task.inputs.context.get("rollback_executed")
        if rollback_executed is not None:
            restored = task.inputs.context.get("rollback_restored", [])
            checks.append(ValidationCheck(
                check_name="rollback_executed",
                check_type="generic",
                passed=True,
                message=f"Rollback executed: {len(restored)} file(s) restored",
            ))

        logger.info("Snapshot validation %s: %d checks", task.task_id, len(checks))
        all_passed = all(c.passed for c in checks)
        return ValidationResult(
            task_id=task.task_id,
            passed=all_passed,
            checks=checks,
            action=ValidationAction.ACCEPT if all_passed else ValidationAction.ABORT,
        )

    def validate_patches_applied(self, task: Task) -> ValidationResult:
        """
        For tasks with file_patches: verify patches were applied,
        target was found, and files are non-empty after patching.
        """
        from pathlib import Path

        applied = task.inputs.context.get("patches_applied", [])
        if not applied:
            return ValidationResult(
                task_id=task.task_id, passed=True,
                checks=[ValidationCheck(
                    check_name="patches_applied",
                    check_type="code",
                    passed=True,
                    message="N/A (no patches to apply)",
                )],
            )

        repo_root = Path(task.inputs.repo).resolve()
        checks: list[ValidationCheck] = []

        for pa in applied:
            fpath = pa.get("path", "")
            mode = pa.get("mode", "")
            status = pa.get("status", "")
            msg = pa.get("message", "")

            checks.append(ValidationCheck(
                check_name=f"patch:{fpath}:{mode}",
                check_type="code",
                passed=status == "applied",
                message=f"{status}: {msg}" if msg else status,
            ))

            if status == "applied":
                full = (repo_root / fpath).resolve()
                if full.exists():
                    size = full.stat().st_size
                    checks.append(ValidationCheck(
                        check_name=f"patched_nonempty:{fpath}",
                        check_type="code",
                        passed=size > 0,
                        message=f"{size} bytes after patch",
                    ))

        all_passed = all(c.passed for c in checks)
        logger.info(
            "Patches validation %s: passed=%s (%d checks)",
            task.task_id, all_passed, len(checks),
        )
        return ValidationResult(
            task_id=task.task_id,
            passed=all_passed,
            checks=checks,
            action=ValidationAction.ACCEPT if all_passed else ValidationAction.RETRY,
        )

    def validate_file_context(self, task: Task) -> ValidationResult:
        """
        For code/hybrid tasks with requested files:
        verify that files_context was populated when files existed.
        """
        from pathlib import Path

        requested = task.inputs.files
        files_context = task.inputs.context.get("files_context", [])
        checks: list[ValidationCheck] = []

        if not requested:
            checks.append(ValidationCheck(
                check_name="file_context_provided",
                check_type="generic",
                passed=True,
                message="N/A (no files explicitly requested)",
            ))
        else:
            repo_root = Path(task.inputs.repo).resolve()
            existing = [f for f in requested if (repo_root / f).exists()]

            if existing and not files_context:
                checks.append(ValidationCheck(
                    check_name="file_context_provided",
                    check_type="code",
                    passed=False,
                    message=f"Files {existing} exist but context is empty",
                ))
            elif existing:
                context_paths = {fc["path"] for fc in files_context}
                covered = [f for f in existing if f in context_paths]
                checks.append(ValidationCheck(
                    check_name="file_context_provided",
                    check_type="code",
                    passed=len(covered) == len(existing),
                    message=f"Context covers {len(covered)}/{len(existing)} requested files",
                ))
            else:
                checks.append(ValidationCheck(
                    check_name="file_context_provided",
                    check_type="code",
                    passed=True,
                    message="Requested files don't exist yet (new file task)",
                ))

        all_passed = all(c.passed for c in checks)
        logger.info(
            "File-context validation %s: passed=%s",
            task.task_id, all_passed,
        )
        return ValidationResult(
            task_id=task.task_id,
            passed=all_passed,
            checks=checks,
            action=ValidationAction.ACCEPT if all_passed else ValidationAction.RETRY,
        )

    def validate_files_applied(self, task: Task) -> ValidationResult:
        """
        For tasks where FileApplier was used: verify files are actually on disk,
        within repo bounds, and non-empty.
        """
        from pathlib import Path

        applied = task.inputs.context.get("files_applied", [])
        if not applied:
            return ValidationResult(
                task_id=task.task_id, passed=True,
                checks=[ValidationCheck(
                    check_name="files_applied",
                    check_type="code",
                    passed=True,
                    message="N/A (no files to apply)",
                )],
            )

        repo_root = Path(task.inputs.repo).resolve()
        checks: list[ValidationCheck] = []

        for fa in applied:
            fpath = fa.get("path", "")
            status = fa.get("status", "")

            if status != "written":
                checks.append(ValidationCheck(
                    check_name=f"file_applied:{fpath}",
                    check_type="code",
                    passed=status == "skipped",
                    message=f"status={status}: {fa.get('message', '')}",
                ))
                continue

            full = (repo_root / fpath).resolve()

            in_bounds = str(full).startswith(str(repo_root))
            checks.append(ValidationCheck(
                check_name=f"file_in_repo:{fpath}",
                check_type="code",
                passed=in_bounds,
                message="within repo" if in_bounds else f"ESCAPES repo: {full}",
            ))

            exists = full.exists()
            checks.append(ValidationCheck(
                check_name=f"file_exists:{fpath}",
                check_type="code",
                passed=exists,
                message="exists on disk" if exists else "MISSING after apply",
            ))

            if exists:
                size = full.stat().st_size
                checks.append(ValidationCheck(
                    check_name=f"file_nonempty:{fpath}",
                    check_type="code",
                    passed=size > 0,
                    message=f"{size} bytes" if size > 0 else "file is empty",
                ))

        all_passed = all(c.passed for c in checks)
        logger.info(
            "Files-applied validation %s: passed=%s (%d checks)",
            task.task_id, all_passed, len(checks),
        )
        return ValidationResult(
            task_id=task.task_id,
            passed=all_passed,
            checks=checks,
            action=ValidationAction.ACCEPT if all_passed else ValidationAction.RETRY,
        )

    def validate_handoff(
        self, task: Task, results: list[AgentResult]
    ) -> ValidationResult:
        """
        For hybrid tasks: verify that commands produced by OpenCode
        were actually received and executed by OpenClaw.
        """
        checks: list[ValidationCheck] = []

        if task.role != TaskRole.HYBRID:
            checks.append(ValidationCheck(
                check_name="handoff",
                check_type="generic",
                passed=True,
                message="N/A (not a hybrid task)",
            ))
            return ValidationResult(
                task_id=task.task_id, passed=True, checks=checks
            )

        opencode_result = None
        openclaw_result = None
        for r in results:
            if r.agent == AgentName.OPENCODE:
                opencode_result = r
            elif r.agent == AgentName.OPENCLAW:
                openclaw_result = r

        if not opencode_result or not openclaw_result:
            checks.append(ValidationCheck(
                check_name="handoff_agents_present",
                check_type="generic",
                passed=False,
                message="Missing OpenCode or OpenClaw result for hybrid task",
            ))
            return ValidationResult(
                task_id=task.task_id,
                passed=False,
                checks=checks,
                action=ValidationAction.RETRY,
            )

        produced = set(opencode_result.artifacts.commands)
        injected = set(task.inputs.commands)
        checks.append(ValidationCheck(
            check_name="handoff_commands_injected",
            check_type="generic",
            passed=produced == injected,
            message=(
                f"Injected {len(injected)} command(s) match OpenCode output"
                if produced == injected
                else f"Mismatch: OpenCode={list(produced)}, injected={list(injected)}"
            ),
        ))

        executed_cmds: set[str] = set()
        for cr in openclaw_result.artifacts.outputs.get("commands_executed", []):
            if isinstance(cr, dict) and cr.get("allowed", False):
                executed_cmds.add(cr["command"])

        received = produced & executed_cmds
        checks.append(ValidationCheck(
            check_name="handoff_commands_executed",
            check_type="generic",
            passed=bool(received),
            message=(
                f"OpenClaw executed {len(received)}/{len(produced)} handed-off command(s)"
                if received
                else "OpenClaw did not execute any of the handed-off commands"
            ),
        ))

        all_passed = all(c.passed for c in checks)

        logger.info(
            "Handoff validation %s: passed=%s (%d checks)",
            task.task_id, all_passed, len(checks),
        )

        return ValidationResult(
            task_id=task.task_id,
            passed=all_passed,
            checks=checks,
            action=ValidationAction.ACCEPT if all_passed else ValidationAction.RETRY,
        )
