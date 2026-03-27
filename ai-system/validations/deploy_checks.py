"""
Exec/deploy-level verify gates.

Required gates for 'exec' and 'hybrid' tasks:
  - command_executed: at least one command was actually run
  - no_total_failure: not all commands failed/blocked
  - verify_commands_ok: commands that OpenCode designated as verify passed
"""

from __future__ import annotations

from typing import Any

from agents.shared.models import AgentName, AgentResult, ValidationCheck


def gate_command_executed(results: list[AgentResult]) -> ValidationCheck:
    """Required: at least one command was actually executed (not just blocked)."""
    for r in results:
        if r.agent != AgentName.OPENCLAW:
            continue
        executed = r.artifacts.outputs.get("commands_executed", [])
        actually_ran = [
            c for c in executed
            if isinstance(c, dict) and c.get("allowed", False)
        ]
        if actually_ran:
            return ValidationCheck(
                check_name="gate:command_executed",
                check_type="exec",
                passed=True,
                message=f"{len(actually_ran)} command(s) executed",
            )

    return ValidationCheck(
        check_name="gate:command_executed",
        check_type="exec",
        passed=False,
        message="No commands were actually executed",
    )


def gate_no_total_failure(results: list[AgentResult]) -> ValidationCheck:
    """Required: not all commands failed or were blocked."""
    for r in results:
        if r.agent != AgentName.OPENCLAW:
            continue
        executed = r.artifacts.outputs.get("commands_executed", [])
        if not executed:
            continue

        ok = [
            c for c in executed
            if isinstance(c, dict) and c.get("allowed") and c.get("exit_code") == 0
        ]
        if ok:
            return ValidationCheck(
                check_name="gate:no_total_failure",
                check_type="exec",
                passed=True,
                message=f"{len(ok)}/{len(executed)} command(s) succeeded",
            )

    return ValidationCheck(
        check_name="gate:no_total_failure",
        check_type="exec",
        passed=False,
        message="All commands failed or were blocked",
    )


def gate_verify_commands_ok(results: list[AgentResult]) -> ValidationCheck:
    """Required for hybrid: verify commands (handed off from OpenCode) passed."""
    for r in results:
        if r.agent != AgentName.OPENCLAW:
            continue
        executed = r.artifacts.outputs.get("commands_executed", [])
        if not executed:
            continue

        all_ok = all(
            c.get("exit_code") == 0
            for c in executed
            if isinstance(c, dict) and c.get("allowed")
        )
        ran_any = any(
            c.get("allowed") for c in executed if isinstance(c, dict)
        )

        if not ran_any:
            return ValidationCheck(
                check_name="gate:verify_commands_ok",
                check_type="exec",
                passed=False,
                message="No verify commands were allowed to run",
            )

        return ValidationCheck(
            check_name="gate:verify_commands_ok",
            check_type="exec",
            passed=all_ok,
            message=(
                "All verify commands passed"
                if all_ok
                else "Some verify commands failed"
            ),
        )

    return ValidationCheck(
        check_name="gate:verify_commands_ok",
        check_type="exec",
        passed=True,
        message="N/A (no OpenClaw result)",
    )
